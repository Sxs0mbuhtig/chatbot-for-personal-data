import time
from services.lexicon import ts_client, COLLECTION_NAME

informal_entries = [
    {
        "headword": "ឡេឡឺ",
        "norm_headword": "ឡេឡឺ",
        "canonical_headword": "ឡេឡឺ",
        "pos": "កិ.គុ.",
        "definition": "អាការធ្វើភ្នែកស្លឺៗ ឬធ្វើមិនដឹងមិនឮ ហាក់ដូចជាភ្លើៗអត់យល់ការណ៍។",
        "source_title": "វចនានុក្រមភាសានិយាយ",
        "is_official_chuon_nath": False,
        "is_variant": False,
        "sort_index": int(time.time())
    },
    {
        "headword": "ឡឺកី",
        "norm_headword": "ឡឺកី",
        "canonical_headword": "ឡឺកី",
        "pos": "កិ.គុ.",
        "definition": "អាការវ៉ល់ៗ ធ្វើឫកពាឡេឡឺមិនប្រាកដប្រជា ឬដើរធ្វើមិនដឹងអត់ខ្វល់។",
        "source_title": "វចនានុក្រមភាសានិយាយ",
        "is_official_chuon_nath": False,
        "is_variant": False,
        "sort_index": int(time.time()) + 1
    },
    {
        "headword": "តេងតាង",
        "norm_headword": "តេងតាង",
        "canonical_headword": "តេងតាង",
        "pos": "កិ.គុ.",
        "definition": "សូរ ឬអាការយោលចុះឡើង ទយតយ រ揺រអាក់ រកទប់លំនឹងមិនបាន (ច្រើនប្រើ៖ តេងតាងៗ)។",
        "source_title": "វចនានុក្រមភាសានិយាយ",
        "is_official_chuon_nath": False,
        "is_variant": False,
        "sort_index": int(time.time()) + 2
    }
]

for doc in informal_entries:
    ts_client.collections[COLLECTION_NAME].documents.upsert(doc)
    print(f"Indexed colloquial entry: {doc['headword']}")
