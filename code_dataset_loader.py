#!/usr/bin/env python3
"""
Code Dataset Loader
Loads and manages the comprehensive code dataset from the python folder.
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import json
import tarfile


class CodeDatasetLoader:
    """Loads and manages the comprehensive code dataset."""
    
    def __init__(self, dataset_path: str = "AIGCodeSet"):
        # Primary directory now points to AIGCodeSet at repo root
        self.dataset_path = Path(dataset_path)
        # Keep alternative paths for backward compatibility if present
        self.alt_path = Path("dataset/python2")
        self.apps_path = Path("dataset/python3")
        self.py150_samples = None  # optional PY150 archive samples (disabled)
        self.program_dataset = None  # AI-Human-Generated-Program-Code dataset
        self.llm_dataset = None
        self.human_dataset = None
        self.combined_dataset = None
        self.features_dataset = None
        self.alt_parquet = None  # optional python2 parquet dataset
        self.apps_train = None   # optional python3 jsonl train
        self.apps_test = None    # optional python3 jsonl test
        self.java_datasets = None  # Java datasets CSV
    
    def load_java_datasets(self) -> bool:
        """Load Java datasets from CSV file."""
        try:
            file_path = self.dataset_path / "javadatasets.csv"
            if not file_path.exists():
                return False
            self.java_datasets = pd.read_csv(file_path)
            return True
        except Exception as e:
            print(f"Error loading Java datasets: {e}")
            return False
    
    def load_llm_dataset(self) -> bool:
        try:
            file_path = self.dataset_path / "created_dataset_with_llms.csv"
            if not file_path.exists():
                return False
            self.llm_dataset = pd.read_csv(file_path)
            return True
        except Exception:
            return False
    
    def load_human_dataset(self) -> bool:
        try:
            file_path = self.dataset_path / "human_selected_dataset.csv"
            if not file_path.exists():
                return False
            self.human_dataset = pd.read_csv(file_path)
            return True
        except Exception:
            return False
    
    def load_combined_dataset(self) -> bool:
        try:
            file_path = self.dataset_path / "all_data_with_ada_embeddings_will_be_splitted_into_train_test_set.csv"
            if not file_path.exists():
                return False
            chunk_size = 10000
            chunks = []
            for chunk in pd.read_csv(file_path, chunksize=chunk_size):
                chunks.append(chunk)
            self.combined_dataset = pd.concat(chunks, ignore_index=True)
            return True
        except Exception:
            return False
    
    def load_alt_parquet(self) -> bool:
        try:
            file_path = self.alt_path / "ai_code_detection.parquet"
            if not file_path.exists():
                return False
            self.alt_parquet = pd.read_parquet(file_path)
            return True
        except Exception:
            return False
    
    def load_apps_jsonl(self) -> bool:
        """Load optional APPS-like dataset from python3 train/test jsonl files."""
        loaded = False
        try:
            train_path = self.apps_path / "train.jsonl"
            if train_path.exists():
                self.apps_train = pd.read_json(train_path, lines=True)
                loaded = True
        except Exception:
            pass
        try:
            test_path = self.apps_path / "test.jsonl"
            if test_path.exists():
                self.apps_test = pd.read_json(test_path, lines=True)
                loaded = True
        except Exception:
            pass
        return loaded

    # PY150 loading disabled
    def load_py150(self, max_files: int = 200) -> bool:
        return False

    def load_program_dataset(self) -> bool:
        """Load AI-Human-Generated-Program-Code-Dataset if present under AIGCodeSet.

        Supports nested directory structure found in the provided folder. Attempts to
        read .csv files and optional .jsonl, inferring 'code' and 'label' columns.
        """
        try:
            base = self.dataset_path / "AI-Human-Generated-Program-Code-Dataset-main"
            # Some zips may double-nest
            if (base / "AI-Human-Generated-Program-Code-Dataset-main").exists():
                base = base / "AI-Human-Generated-Program-Code-Dataset-main"
            if not base.exists() or not base.is_dir():
                return False
            frames: List[pd.DataFrame] = []
            # Load CSVs
            for csv_path in base.glob("*.csv"):
                try:
                    df = pd.read_csv(csv_path)
                    frames.append(df)
                except Exception:
                    continue
            # Load JSONL if present
            jsonl_path = base / "AI-Human-Generated-Program-Code-Dataset.jsonl"
            if jsonl_path.exists():
                try:
                    dfj = pd.read_json(jsonl_path, lines=True)
                    frames.append(dfj)
                except Exception:
                    pass
            if not frames:
                return False
            df_all = pd.concat(frames, ignore_index=True, sort=False)
            # Normalize columns
            cols = {c.lower(): c for c in df_all.columns}
            code_col = cols.get('code') or next((c for c in df_all.columns if 'code' in c.lower()), None)
            label_col = cols.get('label') or next((c for c in df_all.columns if 'label' in c.lower()), None)
            if code_col is None:
                return False
            # If label missing, try map textual class to numeric
            if label_col is None and 'class' in cols:
                label_col = cols['class']
            df_norm = pd.DataFrame({
                'code': df_all[code_col],
                'label': df_all[label_col] if label_col in df_all.columns else None,
            })
            # Coerce label to readable form
            def coerce_label(v):
                s = str(v).strip().lower()
                if s in ('1', 'ai', 'llm', 'generated', 'machine'):
                    return 'AI-generated'
                if s in ('0', 'human', 'manual'):
                    return 'Human-written'
                return 'Unknown'
            if df_norm['label'].isnull().all():
                df_norm['label'] = 'Unknown'
            else:
                df_norm['label'] = df_norm['label'].map(coerce_label)
            self.program_dataset = df_norm
            return True
        except Exception:
            return False
    
    def load_all_datasets(self) -> bool:
        success = False
        success = self.load_java_datasets() or success
        success = self.load_llm_dataset() or success
        success = self.load_human_dataset() or success
        _ = self.load_combined_dataset()
        _ = self.load_alt_parquet() or _
        _ = self.load_apps_jsonl() or _
        # PY150 intentionally not loaded
        _ = self.load_program_dataset() or _
        return success or (self.alt_parquet is not None) or (self.apps_train is not None) or (self.apps_test is not None) or (self.program_dataset is not None)
    
    def get_dataset_summary(self) -> Dict[str, Any]:
        summary = {
            'java_datasets': {},
            'llm_dataset': {},
            'human_dataset': {},
            'combined_dataset': {},
            'python2_parquet': {},
            'python3_apps': {},
            'program_dataset': {},
            # 'py150': {},
            'statistics': {}
        }
        
        if self.java_datasets is not None:
            summary['java_datasets'] = {
                'loaded': True,
                'total_samples': len(self.java_datasets),
                'label_distribution': self.java_datasets['label'].value_counts().to_dict() if 'label' in self.java_datasets.columns else {},
                'topic_distribution': self.java_datasets['topic'].value_counts().to_dict() if 'topic' in self.java_datasets.columns else {},
                'complexity_distribution': self.java_datasets['complexity'].value_counts().to_dict() if 'complexity' in self.java_datasets.columns else {}
            }
        else:
            summary['java_datasets'] = {'loaded': False}
        
        if self.llm_dataset is not None:
            llm_stats = self._analyze_llm_dataset()
            summary['llm_dataset'] = {'loaded': True, 'total_samples': len(self.llm_dataset), 'statistics': llm_stats}
        else:
            summary['llm_dataset'] = {'loaded': False}
        
        if self.human_dataset is not None:
            human_stats = self._analyze_human_dataset()
            summary['human_dataset'] = {'loaded': True, 'total_samples': len(self.human_dataset), 'statistics': human_stats}
        else:
            summary['human_dataset'] = {'loaded': False}
        
        if self.combined_dataset is not None:
            combined_stats = self._analyze_combined_dataset()
            summary['combined_dataset'] = {'loaded': True, 'total_samples': len(self.combined_dataset), 'statistics': combined_stats}
        else:
            summary['combined_dataset'] = {'loaded': False}
        
        if self.alt_parquet is not None:
            df = self.alt_parquet
            label_col = 'label' if 'label' in df.columns else 'Label'
            summary['python2_parquet'] = {
                'loaded': True,
                'total_samples': len(df),
                'columns': list(df.columns)[:12],
                'label_distribution': df[label_col].value_counts().to_dict() if label_col in df.columns else {}
            }
        else:
            summary['python2_parquet'] = {'loaded': False}
        
        if self.apps_train is not None or self.apps_test is not None:
            train_n = len(self.apps_train) if self.apps_train is not None else 0
            test_n = len(self.apps_test) if self.apps_test is not None else 0
            df_any = self.apps_train if self.apps_train is not None else self.apps_test
            cols = list(df_any.columns) if df_any is not None else []
            summary['python3_apps'] = {
                'loaded': True,
                'train_samples': train_n,
                'test_samples': test_n,
                'columns': cols[:10]
            }
        else:
            summary['python3_apps'] = {'loaded': False}
        
        # PY150 summary removed
        if self.program_dataset is not None:
            summary['program_dataset'] = {
                'loaded': True,
                'total_samples': len(self.program_dataset)
            }
        else:
            summary['program_dataset'] = {'loaded': False}
        
        summary['statistics'] = self._calculate_overall_statistics()
        return summary
    
    def _analyze_llm_dataset(self) -> Dict[str, Any]:
        if self.llm_dataset is None:
            return {}
        stats = {
            'total_samples': len(self.llm_dataset),
            'llm_models': self.llm_dataset['LLM'].value_counts().to_dict() if 'LLM' in self.llm_dataset.columns else {},
            'status_distribution': self.llm_dataset['status_in_folder'].value_counts().to_dict() if 'status_in_folder' in self.llm_dataset.columns else {},
            'unique_problems': self.llm_dataset['problem_id'].nunique() if 'problem_id' in self.llm_dataset.columns else None,
            'avg_code_length': self.llm_dataset['code'].str.len().mean() if 'code' in self.llm_dataset.columns else None,
            'languages': self._detect_languages(self.llm_dataset['code']) if 'code' in self.llm_dataset.columns else {}
        }
        return stats
    
    def _analyze_human_dataset(self) -> Dict[str, Any]:
        if self.human_dataset is None:
            return {}
        stats = {
            'total_samples': len(self.human_dataset),
            'status_distribution': self.human_dataset['status_in_folder'].value_counts().to_dict() if 'status_in_folder' in self.human_dataset.columns else {},
            'unique_problems': self.human_dataset['problem_id'].nunique() if 'problem_id' in self.human_dataset.columns else None,
            'unique_users': self.human_dataset['user_id'].nunique() if 'user_id' in self.human_dataset.columns else None,
            'avg_code_length': self.human_dataset['code'].str.len().mean() if 'code' in self.human_dataset.columns else None,
            'languages': self._detect_languages(self.human_dataset['code']) if 'code' in self.human_dataset.columns else {},
        }
        return stats
    
    def _analyze_combined_dataset(self) -> Dict[str, Any]:
        if self.combined_dataset is None:
            return {}
        stats = {
            'total_samples': len(self.combined_dataset),
            'label_distribution': self.combined_dataset['label'].value_counts().to_dict() if 'label' in self.combined_dataset.columns else {},
            'avg_code_length': self.combined_dataset['code'].str.len().mean() if 'code' in self.combined_dataset.columns else None,
        }
        return stats
    
    def _detect_languages(self, code_series: pd.Series) -> Dict[str, int]:
        language_counts = {}
        for code in code_series.head(1000) if code_series is not None else []:
            if pd.isna(code):
                continue
            code_lower = str(code).lower()
            if 'import ' in code_lower or 'def ' in code_lower or 'class ' in code_lower:
                language_counts['Python'] = language_counts.get('Python', 0) + 1
        return language_counts
    
    def _calculate_overall_statistics(self) -> Dict[str, Any]:
        return {
            'total_java_datasets_samples': len(self.java_datasets) if self.java_datasets is not None else 0,
            'total_llm_samples': len(self.llm_dataset) if self.llm_dataset is not None else 0,
            'total_human_samples': len(self.human_dataset) if self.human_dataset is not None else 0,
            'total_combined_samples': len(self.combined_dataset) if self.combined_dataset is not None else 0,
            'total_python2_samples': len(self.alt_parquet) if self.alt_parquet is not None else 0,
            'total_python3_samples': (len(self.apps_train) if self.apps_train is not None else 0) + (len(self.apps_test) if self.apps_test is not None else 0),
            # 'total_py150_samples': len(self.py150_samples) if self.py150_samples is not None else 0,
            'total_program_dataset_samples': len(self.program_dataset) if self.program_dataset is not None else 0,
        }
    
    def get_sample_codes(self, num_samples: int = 5, dataset_type: str = 'mixed') -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        
        # Java datasets support
        if dataset_type == 'java_datasets' and self.java_datasets is not None:
            sample_data = self.java_datasets.sample(min(num_samples, len(self.java_datasets)))
            for _, row in sample_data.iterrows():
                samples.append({
                    'id': f"java_{row.get('topic', 'unknown')}",
                    'code': row.get('code', ''),
                    'label': row.get('label', ''),
                    'language': 'java',
                    'topic': row.get('topic', ''),
                    'complexity': row.get('complexity', ''),
                    'description': row.get('description', '')
                })
            return samples
        
        if dataset_type == 'python3' and (self.apps_train is not None or self.apps_test is not None):
            df = self.apps_train if self.apps_train is not None else self.apps_test
            df = df.sample(min(num_samples, len(df)))
            for _, row in df.iterrows():
                # APPS dataset has many solutions; take the first solution string if list-like string
                code = row.get('solutions')
                try:
                    # handle serialized list
                    if isinstance(code, str) and code and code.strip().startswith('['):
                        code_list = json.loads(code)
                        code = code_list[0] if code_list else ''
                except Exception:
                    pass
                samples.append({
                    'id': f"apps_{row.get('id', '')}",
                    'code': code or '',
                    'label': 'Human-written',  # APPS contains ground-truth solutions; treat as human
                    'question': row.get('question', '')[:120] if isinstance(row.get('question', ''), str) else ''
                })
            return samples
        
        if dataset_type == 'python2' and self.alt_parquet is not None:
            df = self.alt_parquet.sample(min(num_samples, len(self.alt_parquet)))
            label_col = 'label' if 'label' in df.columns else 'Label'
            for _, row in df.iterrows():
                samples.append({
                    'id': f"py2_{row.get('task_name') or ''}",
                    'code': row.get('code', ''),
                    'label': row.get(label_col, ''),
                    'source': row.get('source', ''),
                    'generator': row.get('generator', ''),
                })
            return samples

        # PY150 sampling removed
        
        if dataset_type == 'llm' and self.llm_dataset is not None:
            sample_data = self.llm_dataset.sample(min(num_samples, len(self.llm_dataset)))
            for _, row in sample_data.iterrows():
                samples.append({
                    'id': f"llm_{row.get('submission_id','')}",
                    'code': row.get('code',''),
                    'label': 'AI-generated',
                    'llm_model': row.get('LLM',''),
                    'problem_id': row.get('problem_id',''),
                    'status': row.get('status_in_folder','')
                })
            return samples
        
        if dataset_type == 'human' and self.human_dataset is not None:
            sample_data = self.human_dataset.sample(min(num_samples, len(self.human_dataset)))
            for _, row in sample_data.iterrows():
                samples.append({
                    'id': f"human_{row.get('submission_id','')}",
                    'code': row.get('code',''),
                    'label': 'Human-written',
                    'user_id': row.get('user_id',''),
                    'problem_id': row.get('problem_id',''),
                    'status': row.get('status_in_folder','')
                })
            return samples
        
        # mixed - prioritize Java datasets, then try all available datasets
        if self.java_datasets is not None:
            samples.extend(self.get_sample_codes(num_samples, 'java_datasets'))
            return samples[:num_samples]  # Return immediately with Java samples
        
        if self.llm_dataset is not None:
            samples.extend(self.get_sample_codes(num_samples // 2, 'llm'))
        if self.human_dataset is not None:
            samples.extend(self.get_sample_codes(num_samples - len(samples), 'human'))
        if not samples and self.program_dataset is not None:
            # take random rows
            dfp = self.program_dataset.sample(min(num_samples, len(self.program_dataset)))
            for _, row in dfp.iterrows():
                samples.append({
                    'id': 'program_dataset',
                    'code': row.get('code', ''),
                    'label': row.get('label', 'Unknown'),
                })
        if not samples and self.alt_parquet is not None:
            samples.extend(self.get_sample_codes(num_samples, 'python2'))
        if not samples and (self.apps_train is not None or self.apps_test is not None):
            samples.extend(self.get_sample_codes(num_samples, 'python3'))
        # PY150 fallback removed
        return samples


def main():
    print("Code Dataset Loader Test")
    loader = CodeDatasetLoader()
    ok = loader.load_all_datasets()
    print(f"Loaded any dataset: {ok}")
    print(loader.get_dataset_summary())

if __name__ == "__main__":
    main()
