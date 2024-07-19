import pytest

import pandas as pd

from finaletoolkit.frag.delfi_merge_bins import delfi_merge_bins


def test_merge_bins(request):
    # getting files for comparison
    delfi_bins_csv = request.path.parent / 'data' / 'test_delfi_100kb.csv'
    delfi_merged_bins_csv = request.path.parent / 'data' / 'test_delfi_5mb.csv'

    delfi_bins = pd.read_csv(delfi_bins_csv, dtype={'contig':str, 'start':int, 'stop':int})
    delfi_merged_bins = pd.read_csv(delfi_merged_bins_csv, dtype={'contig':str, 'start':int, 'stop':int})

    merged_bins = delfi_merge_bins(delfi_bins)

    # same number of bins
    assert merged_bins.shape == delfi_merged_bins.shape

    # same bins
    assert (merged_bins['start'] == delfi_merged_bins['start']).all()
    assert (merged_bins['stop'] == delfi_merged_bins['stop']).all()

    # similar ratios
    assert (pytest.approx(merged_bins['ratio_corrected'], rel=5e-2)
            == delfi_merged_bins['ratio_corrected'])
    



