#!/usr/bin/env python3
"""
Data Fetcher - Download and cache Kaggle datasets for crypto analysis
"""

import os
import json
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / 'data' / 'kaggle'
CACHE_FILE = DATA_DIR / 'download_cache.json'

def ensure_data_dir():
    """Ensure data directories exist"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR

def get_cache():
    """Load download cache metadata"""
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}

def save_cache(cache):
    """Save download cache metadata"""
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

def download_with_kagglehub(dataset_ref: str, force=False) -> Path:
    """
    Download a Kaggle dataset using kagglehub
    
    Args:
        dataset_ref: Kaggle dataset reference (e.g., 'mczielinski/bitcoin-historical-data')
        force: Force re-download even if cached
    
    Returns:
        Path to downloaded dataset directory
    """
    try:
        import kagglehub
        
        cache = get_cache()
        
        if not force and dataset_ref in cache:
            cached_path = Path(cache[dataset_ref]['path'])
            if cached_path.exists():
                logger.info(f"Using cached: {dataset_ref}")
                return cached_path
        
        logger.info(f"Downloading: {dataset_ref}")
        path = kagglehub.dataset_download(dataset_ref)
        
        # Update cache
        cache[dataset_ref] = {
            'path': str(path),
            'downloaded_at': datetime.now().isoformat()
        }
        save_cache(cache)
        
        logger.info(f"Downloaded to: {path}")
        return Path(path)
        
    except ImportError:
        logger.error("kagglehub not installed. Run: pip install kagglehub")
        raise
    except Exception as e:
        logger.error(f"Failed to download {dataset_ref}: {e}")
        # Return expected path for manual download
        manual_path = DATA_DIR / dataset_ref.replace('/', '_')
        manual_path.mkdir(exist_ok=True)
        logger.info(f"Created manual download location: {manual_path}")
        return manual_path

def download_all_datasets(force=False):
    """
    Download all required Kaggle datasets
    
    Returns dict mapping dataset names to paths
    """
    ensure_data_dir()
    
    datasets = {
        'btc_1min': 'mczielinski/bitcoin-historical-data',
        'crypto_1min': 'tencars/400-crypto-currency-pairs-1-minute',
        'crypto_prices': 'srk/cryptocurrency-historical-prices',
        'sentiment': 'aminasalamt/crypto-market-intelligence'
    }
    
    paths = {}
    for name, ref in datasets.items():
        try:
            paths[name] = download_with_kagglehub(ref, force)
        except Exception as e:
            logger.warning(f"Could not download {name}: {e}")
            # Create placeholder
            placeholder = DATA_DIR / name
            placeholder.mkdir(exist_ok=True)
            paths[name] = placeholder
    
    return paths

def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Force re-download')
    args = parser.parse_args()
    
    paths = download_all_datasets(force=args.force)
    
    print("\nDataset paths:")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    
    # Check for Kaggle credentials
    kaggle_json = Path.home() / '.kaggle' / 'kaggle.json'
    if not kaggle_json.exists():
        print("\n⚠️  Kaggle credentials not found!")
        print("   1. Get API token from: https://www.kaggle.com/settings")
        print("   2. Save to ~/.kaggle/kaggle.json")
        print("   Or manually download datasets to the paths above")

if __name__ == '__main__':
    main()
