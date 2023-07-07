from __future__ import annotations
import time
from typing import Union, Tuple
from sys import stdout, stderr
from shutil import get_terminal_size
from multiprocessing import Pool
import gzip

import numpy as np
import pysam
import tqdm
from numba import jit

from finaletools.utils import (
    not_read1_or_low_quality, cli_hist, get_intervals
)


def frag_length(
        input_file: Union[str, pysam.AlignmentFile],
        contig: str=None,
        start: int=None,
        stop: int=None,
        output_file: str=None,
        quality_threshold: int=30,
        verbose: bool=False
    ) -> np.ndarray:
    """
    Return `np.ndarray` containing lengths of fragments in `input_file`
    that are above the quality threshold and are proper-paired reads.

    Parameters
    ----------
    input_file : str or pysam.AlignmentFile
        BAM, SAM, or CRAM file containing paired-end fragment reads or
        its path. `AlignmentFile` must be opened in read mode.
    contig : string, optional
    output_file : string, optional
    quality_threshold : int, optional
    verbose : bool, optional

    Returns
    -------
    lengths : numpy.ndarray
        `ndarray` of fragment lengths from file and contig if
        specified.
    """
    if (verbose):
        start_time = time.time()
        stderr.write("Finding frag lengths.\n")

    lengths = []    # list of fragment lengths

    input_is_file = False
    try:
        # handling input types
        if (type(input_file) == pysam.AlignmentFile):
            sam_file = input_file
        elif input_file.endswith('bam') or input_file == '-':
            input_is_file = True
            if (verbose):
                stderr.write(f'Opening {input_file}\n')
            sam_file = pysam.AlignmentFile(input_file)
        else:
            raise ValueError(
                'Invalid input_file type. Only BAM or SAM files are allowed.'
            )

        if (verbose):
            stderr.write('Counting reads')
        count = sam_file.count(contig=contig,
                            start=start,
                            stop=stop) if verbose else None
        if (verbose):
            stderr.write(f'{count} reads counted\n')
        # Iterating on each read in file in specified contig/chromosome
        for read1 in (tqdm.tqdm(sam_file.fetch(contig=contig,
                                        start=start,
                                        stop=stop), total=count)
                    if verbose
                    else sam_file.fetch(contig=contig,
                                        start=start,
                                        stop=stop)):
            # Only select forward strand and filter out non-paired-end
            # reads and low-quality reads
            if (not_read1_or_low_quality(read1, quality_threshold)):
                pass
            else:
                # append length of fragment to list
                lengths.append(abs(read1.template_length))
    finally:
        if input_is_file:
            sam_file.close()

    # convert to array
    lengths = np.array(lengths)

    # check if output specified
    if (type(output_file) == str):
        if output_file.endswith(".bin"): # binary file
            with open(output_file, 'wt') as out:
                lengths.tofile(out)
        elif output_file == '-':
            for line in lengths:
                stdout.write(f'{line}\n')

        else:   # unaccepted file type
            raise ValueError(
                'output_file can only have suffixes .wig or .wig.gz.'
                )

    elif (output_file is not None):
        raise TypeError(
            f'output_file is unsupported type "{type(input_file)}". '
            'output_file should be a string specifying the path of the file '
            'to write output scores to.'
            )

    if (verbose):
        end_time = time.time()
        stderr.write(
            f'frag_length took {end_time - start_time} s to complete\n'
        )

    return lengths


def frag_length_bins(
    input_file: Union[str, pysam.AlignmentFile],
    contig: str=None,
    start: int=None,
    stop: int=None,
    bin_size: int=None,
    output_file: str=None,
    contig_by_contig: bool=False,
    histogram: bool=False,
    quality_threshold: int=30,
    verbose: Union[bool, int]=False
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Takes input_file, computes frag lengths of fragments and returns
    two arrays containing bins and counts by size. Optionally prints
    data to output as a tab delimited table or histogram.

    Parameters
    ----------
    input_file : str or AlignmentFile
    contig : str, optional
    start : int, optional
    stop : int, optional
    bin_size : int, optional
    output_file : str, optional
    workers : int, optional

    Returns
    -------
    bins : ndarray
    counts : ndarray
    """
    if verbose:
        stderr.write(
            f"""
            input_file: {input_file}
            contig: {contig}
            start: {start}
            stop: {stop}
            bin_size: {bin_size}
            output_file: {output_file}
            contig_by_contig: {contig_by_contig}
            histogram: {histogram}
            quality_threshold: {quality_threshold}
            verbose: {verbose}
            \n"""
        )
        start_time = time.time()

    # generating fragment lengths
    frag_lengths = frag_length(
        input_file,
        contig,
        start,
        stop,
        quality_threshold=quality_threshold,
        verbose=verbose-1 if verbose>1 else 0
    )
    # get statistics
    stats = []
    stats.append(('mean', np.mean(frag_lengths)))
    stats.append(('median', np.median(frag_lengths)))
    stats.append(('stdev', np.std(frag_lengths)))
    stats.append(('min', np.min(frag_lengths)))
    stats.append(('max', np.max(frag_lengths)))

    # generating bins and counts
    if bin_size is None:
        if histogram:
            term_width, term_height = get_terminal_size((80, 24))
            n_bins = term_width - 24

            start = np.min(frag_lengths)
            stop = np.max(frag_lengths)

            bin_size = round((stop - start) / n_bins)
        else:
            bin_size = 5

    start = np.min(frag_lengths)
    stop = np.max(frag_lengths)
    n_bins = (stop - start) // bin_size

    bins = np.arange(start, stop, bin_size)
    counts = []

    # generate histogram
    for bin in bins:
        count = np.sum(
            (frag_lengths >= bin)
            * (frag_lengths < (bin + bin_size))
        )
        counts.append(count)
    bins = np.append(bins, stop)

    if output_file is not None:
        try:
            out_is_file = False
            if output_file == '-':
                out = stdout
            elif output_file.endswith('.gz'):
                out_is_file = True
                out = gzip.open(output_file, 'w')
            else:
                out_is_file = True
                out = open(output_file, 'w')

            if histogram:
                cli_hist(bins, counts, n_bins, stats, out)

            else:
                out.write('min\tmax\tcount\n')
                for bin, count in zip(bins, counts):
                    out.write(f'{bin}\t{bin+bin_size}\t{count}\n')
        finally:
            if out_is_file:
                out.close()
    elif histogram:
        if contig is not None:
            title = f'Fragment Lengths for {contig}:{start}-{stop}'
        else:
            title = f'Fragment Lengths'
        cli_hist(bins, counts, n_bins, stats, stdout, title)

    if verbose:
        stop_time = time.time()
        stderr.write(
            f'frag_length_bins took {stop_time-start_time} s to complete.\n'
        )

    return bins, counts


def _frag_length_stats(
    input_file: Union(str, pysam.AlignmentFile),
    contig: str,
    start: int,
    stop: int,
    name: str,
    quality_threshold: int,
    verbose: Union(bool, int)
):
    # generating fragment lengths
    frag_lengths = frag_length(
        input_file,
        contig,
        start,
        stop,
        quality_threshold=quality_threshold,
        verbose=verbose
    )
    if frag_lengths.shape[0] == 0:
        mean, median, stdev, min, max = 5*[-1]
    else:
        mean = np.mean(frag_lengths)
        median = np.median(frag_lengths)
        stdev = np.std(frag_lengths)
        min = np.min(frag_lengths)
        max = np.max(frag_lengths)

    return name, contig, start, stop, mean, median, stdev, min, max


def _frag_length_stats_star(args):
    return _frag_length_stats(*args)


def frag_length_intervals(
    input_file: Union[str, pysam.AlignmentFile],
    interval_file: str,
    output_file: str=None,
    quality_threshold: int=30,
    workers: int=1,
    verbose: Union[bool, int]=False
):
    """
    Takes fragments from BAM file and calculates fragment length
    statistics for each interval in a BED file. If output specified,
    results will be printed into a tab-delimited file.

    Parameters
    ----------
    input_file : str or AlignmentFile
    interval_file : str
    output_file : str, optional
    quality_threshold : int, optional
    workers : int, optional
    verbose : boo or int, optional

    Returns
    -------
    """
    if verbose:
        stderr.write(
            f"""
            input_file: {input_file}
            interval_file: {interval_file}
            output_file: {output_file}
            quality_threshold: {quality_threshold}
            workers: {workers}
            verbose: {verbose}
            \n"""
        )
        start_time = time.time()

    # read interval_file into list of tuples
    intervals = get_intervals(
        input_file,
        interval_file,
        quality_threshold,
        verbose=verbose
    )

    interval_len = len(intervals)
    if verbose:
        stderr.write(f'{interval_len} intervals read!\n')

    try:
        # create pool and submit intervals into processess
        pool = Pool(workers)
        iter_results = pool.imap(
            _frag_length_stats_star,
            tqdm.tqdm(
                intervals,
                desc='Filling process pool',
                position=0
            ) if verbose else intervals,
            round(interval_len/workers/2+1)
        )
        # write to output
        try:
            output_is_file = False
            if output_file == '-':
                out = stdout
            else:
                output_is_file = True
                out = open(output_file, 'w')
            # header
            out.write(
                'name\tcontig\tstart\tstop\tmean\tmedian\tstdev\tmin\tmax\n'
            )
            for result in tqdm.tqdm(
                iter_results,
                total=interval_len,
                desc='Writing to out',
                position=2
            ) if verbose else iter_results:
                out.write('\t'.join([str(item) for item in result]))
                out.write('\n')
        finally:
            if output_is_file:
                out.close()

        results = [result for result in iter_results]

    finally:
        pool.close()

    if verbose:
        stop_time = time.time()
        stderr.write(
            f'frag_length_intervals took {stop_time-start_time} s\n'
        )

    return results