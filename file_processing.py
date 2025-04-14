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
            # Для совместимости со старым форматом
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
        # Загружаем существующие данные
        existing_data = load_existing_data()
        
        # Проверяем, не обрабатывался ли файл ранее
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
                if df.empty or len(df.columns) < 5:
                    continue
                    
                df.columns = df.iloc[0]
                df = df[1:]
                
                required_columns = {
                    'Дата': 'date',
                    'Название предмета': 'subject',
                    'Преподаватель': 'teacher',
                    'Часы': 'time',
                    'Ауд.': 'audience'
                }
                
                # Проверяем наличие всех необходимых колонок
                missing_columns = [col for col in required_columns.keys() if col not in df.columns]
                if missing_columns:
                    print(f"Лист '{sheet_name}': отсутствуют колонки {', '.join(missing_columns)}")
                    continue
                
                for _, row in df.iterrows():
                    try:
                        # Пропускаем строки с пустыми значениями
                        if any(pd.isna(row[col]) for col in required_columns.keys()):
                            continue
                            
                        date_value = row['Дата']
                        date_str = date_value.strftime('%d.%m') if isinstance(date_value, datetime) else str(date_value).split()[0]
                        
                        new_entry = {
                            'sheet': sheet_name,
                            'date': date_str,
                            'subject': str(row['Название предмета']),
                            'teacher': str(row['Преподаватель']),
                            'time': str(row['Часы']),
                            'audience': str(row['Ауд.']),
                            'source_file': file_name
                        }
                        
                        # Проверяем на дубликаты
                        is_duplicate = any(
                            entry['date'] == new_entry['date'] and 
                            entry['subject'] == new_entry['subject'] and
                            entry['teacher'] == new_entry['teacher']
                            for entry in existing_data["schedule_data"]
                        )
                        
                        if not is_duplicate:
                            new_entries.append(new_entry)
                    except Exception as e:
                        print(f"Ошибка обработки строки: {e}")
                        continue
            except Exception as e:
                print(f"Ошибка обработки листа {sheet_name}: {e}")
                continue
        
        # Обновляем данные
        existing_data["meta"]["processed_files"].append(file_name)
        existing_data["schedule_data"].extend(new_entries)
        
        return {
            "status": "success",
            "data": existing_data,
            "new_entries_count": len(new_entries),
            "total_entries": len(existing_data["schedule_data"]),
            "total_files": len(existing_data["meta"]["processed_files"])
        }
            
    except Exception as e:
        print(f"Error processing Excel file: {e}")
        return {
            "status": "error",
            "message": str(e)
        }