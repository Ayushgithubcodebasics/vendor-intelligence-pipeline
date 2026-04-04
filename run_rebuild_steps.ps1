python -m src.rebuild_pipeline --step vendor_map
python -m src.rebuild_pipeline --step purchase_prices
python -m src.rebuild_pipeline --step purchases
python -m src.rebuild_pipeline --step sales
python -m src.rebuild_pipeline --step freight
python -m src.rebuild_pipeline --step finalize
