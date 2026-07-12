from datasets import load_dataset

ds = load_dataset('abisee/cnn_dailymail', '3.0.0', split='train[:3]')
for i, row in enumerate(ds):
    print(f'--- Article {i} ---')
    print('Keys:', list(row.keys()))
    print('ID:', row['id'])
    print('Article (first 300 chars):', row['article'][:300])
    print('Highlights:', row['highlights'][:300])
    print()