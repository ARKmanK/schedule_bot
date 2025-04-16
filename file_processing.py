import pandas as pd
import json
import os
from datetime import datetime
from io import BytesIO

def load_existing_data():
    """Загружает существующие данные из файла"""
    if os.path.exists('data/schedule.json'):
        with open('data/schedule.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return {
                    "meta": {
                        "processed_files": [],
                        "version": 1
                    },
                    "schedule_data": data
                }
            return data
    return {
        "meta": {
            "processed_files": [],
            "version": 1
        },
        "schedule_data": []
    }

def save_data(data):
    """Сохраняет данные в файл"""
    os.makedirs('data', exist_ok=True)
    with open('data/schedule.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def process_excel_file(file_bytes: bytes, file_name: str) -> dict:
    try:
        existing_data = load_existing_data()
        
        if file_name in existing_data["meta"]["processed_files"]:
            return {
                "status": "error",
                "message": f"Файл {file_name} уже был обработан ранее"
            }
            
        xls = pd.ExcelFile(BytesIO(file_bytes))
        new_entries = []
        
        for sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None, skiprows=14)
                if df.empty or len(df.columns) < 6:
                    continue
                    
                headers = df.iloc[0].tolist()
                column_mapping = {}
                for i, header in enumerate(headers):
                    if pd.isna(header) or str(header).strip() == '':
                        column_mapping[i] = 'type'
                    elif str(header).strip() == 'Дата':
                        column_mapping[i] = 'date'
                    elif str(header).strip() == 'Название предмета':
                        column_mapping[i] = 'subject'
                    elif str(header).strip() == 'Преподаватель':
                        column_mapping[i] = 'teacher'
                    elif str(header).strip() == 'Часы':
                        column_mapping[i] = 'time'
                    elif str(header).strip() == 'Ауд.':
                        column_mapping[i] = 'audience'
                
                df = df.rename(columns=column_mapping)
                df = df[1:]
                
                required_columns = ['date', 'subject', 'teacher', 'time', 'audience']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    continue
                
                has_type = 'type' in df.columns
                
                for _, row in df.iterrows():
                    try:
                        if pd.isna(row['date']) or pd.isna(row['subject']) or pd.isna(row['teacher']):
                            continue
                            
                        date_value = row['date']
                        date_str = date_value.strftime('%d.%m') if isinstance(date_value, datetime) else str(date_value).split()[0]
                        
                        new_entry = {
                            'sheet': sheet_name,
                            'date': date_str,
                            'subject': str(row['subject']),
                            'teacher': str(row['teacher']),
                            'time': str(row['time']),
                            'audience': str(row['audience'])
                        }
                        
                        if has_type and not pd.isna(row.get('type')):
                            new_entry['type'] = str(row['type'])
                        
                        is_duplicate = any(
                            entry['date'] == new_entry['date'] and 
                            entry['subject'] == new_entry['subject'] and
                            entry['teacher'] == new_entry['teacher']
                            for entry in existing_data["schedule_data"]
                        )
                        
                        if not is_duplicate:
                            new_entries.append(new_entry)
                    except Exception as e:
                        continue
            except Exception as e:
                continue
        
        existing_data["meta"]["processed_files"].append(file_name)
        existing_data["schedule_data"].extend(new_entries)
        
        return {
            "status": "success",
            "data": existing_data,
            "new_entries_count": len(new_entries)
        }
            
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }