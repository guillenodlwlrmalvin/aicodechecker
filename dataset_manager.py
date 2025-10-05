#!/usr/bin/env python3
"""
Dataset Manager
Manages the integration of Excel/CSV datasets with the AI detection system.
"""

import os
import sys
import pandas as pd
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from text_detector import TextDetector, TextDatasetLoader


class DatasetManager:
    """Manages dataset operations and integration."""
    
    def __init__(self, dataset_path: str = "dataset"):
        self.dataset_path = Path(dataset_path)
        self.text_loader = TextDatasetLoader(dataset_path)
        self.text_detector = TextDetector()
    
    def load_all_datasets(self) -> bool:
        """Load all available datasets."""
        success = True
        
        # Load text dataset
        if not self.text_loader.load_dataset():
            print("Warning: Failed to load text dataset")
            success = False
        
        return success
    
    def get_dataset_summary(self) -> Dict[str, Any]:
        """Get summary of all loaded datasets."""
        summary = {
            'text_dataset': {},
            'code_dataset': {}
        }
        
        # Text dataset summary
        if self.text_loader.train_essays is not None:
            text_stats = self.text_loader.get_dataset_stats()
            summary['text_dataset'] = {
                'loaded': True,
                'stats': text_stats,
                'files': {
                    'train_essays': 'train_essays.csv',
                    'test_essays': 'test_essays.csv',
                    'train_prompts': 'train_prompts.csv',
                    'sample_submission': 'sample_submission.csv'
                }
            }
        else:
            summary['text_dataset'] = {'loaded': False}
        
        # Code dataset summary (from existing structure)
        code_human_path = self.dataset_path / "human"
        code_ai_path = self.dataset_path / "ai"
        
        if code_human_path.exists() and code_ai_path.exists():
            human_files = list(code_human_path.glob("*.py")) + list(code_human_path.glob("*.js"))
            ai_files = list(code_ai_path.glob("*.py")) + list(code_ai_path.glob("*.js"))
            
            summary['code_dataset'] = {
                'loaded': True,
                'stats': {
                    'human_samples': len(human_files),
                    'ai_samples': len(ai_files),
                    'total_samples': len(human_files) + len(ai_files)
                },
                'files': {
                    'human_samples': [f.name for f in human_files],
                    'ai_samples': [f.name for f in ai_files]
                }
            }
        else:
            summary['code_dataset'] = {'loaded': False}
        
        return summary
    
    def validate_text_dataset(self) -> Dict[str, Any]:
        """Validate the text dataset using the text detector."""
        if not self.text_loader.train_essays is not None:
            return {'error': 'Text dataset not loaded'}
        
        return self.text_loader.validate_dataset(self.text_detector)
    
    def generate_sample_predictions(self, num_samples: int = 5) -> List[Dict[str, Any]]:
        """Generate sample predictions for demonstration."""
        if self.text_loader.test_essays is None:
            return []
        
        samples = []
        test_data = self.text_loader.test_essays.head(num_samples)
        
        for _, row in test_data.iterrows():
            text = row['text']
            result = self.text_detector.analyze_text(text)
            
            samples.append({
                'id': row['id'],
                'prompt_id': row['prompt_id'],
                'text_preview': text[:200] + "..." if len(text) > 200 else text,
                'prediction': result['label'],
                'score': result['score'],
                'confidence': result['confidence']
            })
        
        return samples
    
    def export_validation_results(self, output_path: str = None) -> str:
        """Export validation results to a file."""
        if output_path is None:
            output_path = self.dataset_path / "test_results" / "text_validation_results.json"
        
        output_path = Path(output_path)
        output_path.parent.mkdir(exist_ok=True)
        
        # Get validation results
        validation_results = self.validate_text_dataset()
        
        # Get dataset summary
        summary = self.get_dataset_summary()
        
        # Get sample predictions
        sample_predictions = self.generate_sample_predictions()
        
        results = {
            'validation_results': validation_results,
            'dataset_summary': summary,
            'sample_predictions': sample_predictions,
            'timestamp': pd.Timestamp.now().isoformat()
        }
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        return str(output_path)
    
    def create_integration_report(self) -> str:
        """Create a comprehensive integration report."""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("AI DETECTION SYSTEM - DATASET INTEGRATION REPORT")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Dataset summary
        summary = self.get_dataset_summary()
        
        report_lines.append("DATASET SUMMARY:")
        report_lines.append("-" * 40)
        
        # Text dataset
        if summary['text_dataset']['loaded']:
            text_stats = summary['text_dataset']['stats']
            report_lines.append(f"Text Dataset: LOADED")
            report_lines.append(f"  - Total essays: {text_stats['total_essays']}")
            report_lines.append(f"  - Human essays: {text_stats['human_essays']}")
            report_lines.append(f"  - AI essays: {text_stats['ai_essays']}")
            report_lines.append(f"  - Test essays: {text_stats['test_essays']}")
            report_lines.append(f"  - Prompts: {text_stats['prompts']}")
        else:
            report_lines.append("Text Dataset: NOT LOADED")
        
        report_lines.append("")
        
        # Code dataset
        if summary['code_dataset']['loaded']:
            code_stats = summary['code_dataset']['stats']
            report_lines.append(f"Code Dataset: LOADED")
            report_lines.append(f"  - Human samples: {code_stats['human_samples']}")
            report_lines.append(f"  - AI samples: {code_stats['ai_samples']}")
            report_lines.append(f"  - Total samples: {code_stats['total_samples']}")
        else:
            report_lines.append("Code Dataset: NOT LOADED")
        
        report_lines.append("")
        
        # Validation results
        if summary['text_dataset']['loaded']:
            report_lines.append("TEXT DATASET VALIDATION:")
            report_lines.append("-" * 40)
            
            validation_results = self.validate_text_dataset()
            if 'error' not in validation_results:
                report_lines.append(f"Accuracy: {validation_results['accuracy']:.2%}")
                report_lines.append(f"Total samples: {validation_results['total_samples']}")
                report_lines.append(f"Correct predictions: {validation_results['correct_predictions']}")
            else:
                report_lines.append(f"Validation error: {validation_results['error']}")
        
        report_lines.append("")
        
        # Sample predictions
        if summary['text_dataset']['loaded']:
            report_lines.append("SAMPLE PREDICTIONS:")
            report_lines.append("-" * 40)
            
            sample_predictions = self.generate_sample_predictions(3)
            for i, sample in enumerate(sample_predictions, 1):
                report_lines.append(f"{i}. ID: {sample['id']}")
                report_lines.append(f"   Prediction: {sample['prediction']} ({sample['score']:.1f}%)")
                report_lines.append(f"   Text: {sample['text_preview']}")
                report_lines.append("")
        
        # Integration status
        report_lines.append("INTEGRATION STATUS:")
        report_lines.append("-" * 40)
        report_lines.append("+ Text detection module created")
        report_lines.append("+ Database models updated")
        report_lines.append("+ Web interface updated")
        report_lines.append("+ Dataset loading functionality")
        report_lines.append("+ Validation system")
        report_lines.append("")
        
        report_lines.append("NEXT STEPS:")
        report_lines.append("-" * 40)
        report_lines.append("1. Test the web interface with sample text")
        report_lines.append("2. Run validation on the full dataset")
        report_lines.append("3. Fine-tune detection parameters if needed")
        report_lines.append("4. Consider adding more detection methods")
        report_lines.append("")
        
        report_text = "\n".join(report_lines)
        
        # Save report
        report_path = self.dataset_path / "test_results" / "integration_report.txt"
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w') as f:
            f.write(report_text)
        
        return report_text


def main():
    """Main function to demonstrate dataset integration."""
    print("AI Detection System - Dataset Integration")
    print("=" * 50)
    
    # Initialize dataset manager
    manager = DatasetManager()
    
    # Load datasets
    print("Loading datasets...")
    if manager.load_all_datasets():
        print("+ Datasets loaded successfully")
    else:
        print("! Some datasets failed to load")
    
    print()
    
    # Get summary
    print("Dataset Summary:")
    summary = manager.get_dataset_summary()
    
    if summary['text_dataset']['loaded']:
        text_stats = summary['text_dataset']['stats']
        print(f"  Text Dataset: {text_stats['total_essays']} essays "
              f"({text_stats['human_essays']} human, {text_stats['ai_essays']} AI)")
    
    if summary['code_dataset']['loaded']:
        code_stats = summary['code_dataset']['stats']
        print(f"  Code Dataset: {code_stats['total_samples']} samples "
              f"({code_stats['human_samples']} human, {code_stats['ai_samples']} AI)")
    
    print()
    
    # Validate text dataset
    if summary['text_dataset']['loaded']:
        print("Validating text dataset...")
        validation_results = manager.validate_text_dataset()
        if 'error' not in validation_results:
            print(f"+ Validation complete: {validation_results['accuracy']:.2%} accuracy")
        else:
            print(f"- Validation failed: {validation_results['error']}")
    
    print()
    
    # Generate integration report
    print("Generating integration report...")
    report = manager.create_integration_report()
    print("+ Integration report generated")
    
    # Export validation results
    print("Exporting validation results...")
    results_path = manager.export_validation_results()
    print(f"+ Results exported to: {results_path}")
    
    print()
    print("Integration complete! Check the generated reports for details.")


if __name__ == "__main__":
    main()
