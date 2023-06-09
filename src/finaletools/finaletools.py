"""
Author: James Li
Created: 6/2/23
PI: Yaping Liu

Description:
Python script to calculate fragment features given a BAM file.

"""
# TODO: typing annotations for all functions

import pysam
import argparse
import gzip
import numpy as np
from multiprocessing.pool import Pool
import time
from typing import Union

def frag_bam_to_bed(input_file, output_file, contig=None, quality_threshold=15, verbose=False):
    """
    Take paired-end reads from bam_file and write to a BED file.

    Parameters
    ----------
    input_file : pysam.AlignedFile or str
    out_file : str
    contig : str, optional
    quality_threshold : int, optional
    verbose : bool, optional
    """
    sam_file = None
    try:
        # Open file or asign AlignmentFile to sam_file
        if (type(input_file) == pysam.AlignmentFile):
            sam_file = input_file            
        elif (type(input_file) == str):
            sam_file = pysam.AlignmentFile(input_file)
        else:
            raise TypeError("bam_file should be a SAM or BAM file or a string containing a path to the file.")
        
        # Open output file
        if output_file.endswith('.gz'):
            out = gzip.open(output_file, 'wt')
        else:
            out = open(output_file, 'w')

        # iterate through reads and send to BED
        for read1 in sam_file.fetch(contig=contig):
            if read1.is_read2 or low_quality_read_pairs(read1, quality_threshold):  # Only select forward strand and filter out non-paired-end reads and low-quality reads
                pass
            else:
                out.write(f'{read1.reference_name}\t{read1.reference_start}\t{read1.reference_start + read1.template_length}\n')
    except Exception as e:
        print("An error occurred:", str(e))
    
    finally:
        # Close everything when done
        if (type(input_file) == str):
            sam_file.close()
        out.close()



def low_quality_read_pairs(read, min_mapq=15): # min_mapq is synonymous to quality_threshold, copied from https://github.com/epifluidlab/cofragr/blob/master/python/frag_summary_in_intervals.py
    """
    Return `True` if the sequenced read described in `read` is not a mapped properly paired read with a Phred score exceeding `min_mapq`.

    Parameters
    ----------
    read : pysam.AlignedSegment
        Sequenced read to check for quality, perfect pairing and if it is mapped.
    min_mapq : int, optional
        Minimum Phred score for map quality of read. Defaults to 15.

    Returns
    -------
    is_low_quality : bool
        True if read is low quality, unmapped, not properly paired.
    """

    return read.is_unmapped or read.is_secondary or (not read.is_paired) \
           or read.mate_is_unmapped or read.is_duplicate or read.mapping_quality < min_mapq \
           or read.is_qcfail or read.is_supplementary or (not read.is_proper_pair) \
           or read.reference_name != read.next_reference_name


def frag_length(input_file, contig=None, output_file=None, threads=1, quality_threshold=15, verbose=False):
    """
    Return `np.ndarray` containing lengths of fragments in `input_file` that are
    above the quality threshold and are proper-paired reads.

    Parameters
    ----------
    input_file : str or pysam.AlignmentFile
        BAM, SAM, or CRAM file containing paired-end fragment reads or its 
        path. `AlignmentFile` must be opened in read mode.
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

    lengths = []    # list of fragment lengths
    if (type(input_file) == pysam.AlignmentFile):
        sam_file = input_file
        for read1 in sam_file.fetch(contig=contig): # Iterating on each read in file in specified contig/chromosome
            if read1.is_read2 or low_quality_read_pairs(read1, quality_threshold):  # Only select forward strand and filter out non-paired-end reads and low-quality reads
                pass
            else:
                lengths.append(abs(read1.template_length))  # append length of fragment to list
    else:
        with pysam.AlignmentFile(input_file) as sam_file:   # Import
            for read1 in sam_file.fetch(contig=contig): # Iterating on each read in file in specified contig/chromosome
                if read1.is_read2 or low_quality_read_pairs(read1, quality_threshold):  # Only select forward strand and filter out non-paired-end reads and low-quality reads
                    pass
                else:
                    lengths.append(abs(read1.template_length))  # append length of fragment to list
    # TODO: when given output file, print to file

    if (verbose):
        end_time = time.time()
        print(f'frag_coverage took {end_time - start_time} s to complete')
    return np.array(lengths)

# TODO: Read about pile-up

def frag_center_coverage(input_file, contig, start, stop, output_file=None, quality_threshold=15, verbose=False):
    """
    Return estimated fragment coverage over specified `contig` and region of 
    `input_file`. Uses an algorithm where the midpoints of fragments are calculated
    and coverage is tabulated from the midpoints that fall into the specified
    region. Not suitable for fragments of size approaching region size.

    Parameters
    ----------
    input_file : str or pysam.AlignmentFile
        BAM, SAM, or CRAM file containing paired-end fragment reads or its 
        path. `AlignmentFile` must be opened in read mode.
    contig : string
    start : int
    stop : int
    output_file : string, optional
    quality_threshold : int, optional
    verbose : bool, optional

    Returns
    -------
    coverage : int
        Fragment coverage over contig and region.
    """
    # TODO: determine if reference (like as found in pysam) is necessary
    # TODO: consider including region string (like in pysam)

    if (verbose):
        start_time = time.time()

    coverage = 0 # initializing variable for coverage tuple outside of with statement

    if (type(input_file) == pysam.AlignmentFile):
        sam_file = input_file
        for read1 in sam_file.fetch(contig=contig): # Iterating on each read in file in specified contig/chromosome
            if read1.is_read2 or low_quality_read_pairs(read1, quality_threshold):  # Only select forward strand and filter out non-paired-end reads and low-quality reads
                pass
            else:
                # calculate mid-point of fragment
                center = read1.reference_start + read1.template_length // 2
                if ((center >= start) and (center < stop)):
                    coverage += 1
    else:
        with pysam.AlignmentFile(input_file, 'r') as sam_file:   # Import
            for read1 in sam_file.fetch(contig=contig): # Iterating on each read in file in specified contig/chromosome
                if read1.is_read2 or low_quality_read_pairs(read1, quality_threshold):  # Only select forward strand and filter out non-paired-end reads and low-quality reads
                    pass
                else:
                    # calculate mid-point of fragment
                    center = read1.reference_start + read1.template_length // 2
                    if ((center >= start) and (center < stop)):
                        coverage += 1
    if (verbose):
        end_time = time.time()
        print(f'frag_coverage took {end_time - start_time} s to complete')

    return coverage

def wps(input_file: Union[str, pysam.AlignmentFile], contig:str, start: Union[int, str], stop: Union[int, str], output_file: str=None, window_size: int=120, quality_threshold: int=15, verbose: bool=False) -> np.ndarray[np.int64, np.int64]: # Using Union instead of bitwise | to allow backward compatability if needed
    """
    Return Windowed Protection Scores as specified in Snyder et al (2016) over a
    region [start,stop).

    Parameters
    ----------
    input_file : str or pysam.AlignmentFile
        BAM or SAM file containing paired-end fragment reads or its 
        path. `AlignmentFile` must be opened in read mode.
    contig : str
    start : int
    stop : int
    output_file : string, optional
    window_size : int, optional
    quality_threshold : int, optional
    verbose : bool, optional

    Returns
    -------
    scores : numpy.ndarray
        np array of shape (n, 2) where column 1 is the coordinate and column 2 is the score
        and n is the number of coordinates in region [start,stop)
    """

    if (verbose):
        start_time = time.time()
    
    # set start and stop to ints
    start = int(start)
    stop = int(stop)

    # lists tuples containing coordinates of fragment ends.
    frag_ends = []

    if (type(input_file) == pysam.AlignmentFile):   # input_file is AllignmentFile
        sam_file = input_file
        for read1 in sam_file.fetch(contig=contig):
            if read1.is_read2 or low_quality_read_pairs(read1, quality_threshold):  # Only select forward strand and filter out non-paired-end reads and low-quality reads
                pass
            else:
                frag_ends.append((read1.reference_start, read1.reference_start + read1.template_length))

    elif (type(input_file) == str): # input_file is a path string
        with pysam.AlignmentFile(input_file, 'r') as sam_file:   # Import
            for read1 in sam_file.fetch(contig=contig):
                if read1.is_read2 or low_quality_read_pairs(read1, quality_threshold):  # Only select forward strand and filter out non-paired-end reads and low-quality reads
                    pass
                else:
                    frag_ends.append((read1.reference_start, read1.reference_start + read1.template_length))
    
    else:
        raise TypeError(f'input_file is unsupported type "{type(input_file)}". input_file should be a pysam.AlignmentFile or a string containing the path to a SAM or BAM file.')

    # convert to ndarray
    frag_ends = np.array(frag_ends)

    # if (verbose):
    #     print(frag_ends)

    # array to store positions and scores
    scores = np.zeros((stop-start, 2))
    window_centers = np.arange(start, stop, dtype=np.int64)
    scores[:, 0] = window_centers

    for i in range(stop-start):
        # get window position associated with index i from first column
        window_pos = window_centers[i]

        # start and stop coordinates of the window
        window_start = round(window_pos - window_size * 0.5)
        window_stop = round(window_pos + window_size * 0.5 - 1) # inclusive

        # count number of totally spanning fragments
        is_spanning = (frag_ends[:, 0] < window_start) * (frag_ends[:, 1] > window_stop)
        num_spanning = np.sum(is_spanning)

        # count number of fragments with end in window
        is_start_in = (frag_ends[:, 0] >= window_start) * (frag_ends[:, 0] <= window_stop)
        is_stop_in = (frag_ends[:, 0] >= window_start) * (frag_ends[:, 0] <= window_stop)
        is_end_in = np.logical_or(is_start_in, is_stop_in)
        num_end_in = np.sum(is_end_in)

        # calculate score and put in second column
        scores[i, 1] = num_spanning - num_end_in

        # if (verbose):
        #     print(f'window pos {window_pos}, window ends {window_start} {window_stop}, spanning {num_spanning}, end in {num_end_in}, WPS {scores[i, 1]}')

    # TODO: consider switch-case statements and determine if they shouldn't be used for backwards compatability
    if (type(output_file) == str):   # check if output specified

        if output_file.endswith(".wig.gz"): # zipped wiggle
            with gzip.open(output_file, 'wt') as out:
                # declaration line
                out.write(f'fixedStep\tchrom={contig}\tstart={start}\tstep={1}\tspan={stop-start}\n')
                for score in scores[:, 1]:
                    out.write(f'{score}\n')

        elif output_file.endswith(".wig"):  # wiggle
            with open(output_file, 'wt') as out:
                # declaration line
                out.write(f'fixedStep\tchrom={contig}\tstart={start}\tstep={1}\tspan={stop-start}\n')
                for score in scores[:, 1]:
                    out.write(f'{score}\n')

        else:   # unaccepted file type
            raise ValueError('output_file can only have suffixes .wig or .wig.gz.')

    elif (output_file != None):
        raise TypeError(f'output_file is unsupported type "{type(input_file)}". output_file should be a string specifying the path of the file to output scores to.')

    if (verbose):
        end_time = time.time()
        print(f'frag_coverage took {end_time - start_time} s to complete')
        
    return scores

# TODO: look through argparse args and fix them all
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='finaletools',
                    description='Calculates fragmentation features given a CRAM/BAM/SAM file',
                    epilog='')
    subparsers = parser.add_subparsers(title='subcommands', description="Subcommands of finaletools", dest='subcommand')

    # Common arguments
    parser.add_argument('contig')   # chromosome of window
    parser.add_argument('input_file')    # input bam file to calculate coverage from
    parser.add_argument('--output_file') # optional output text file to print coverage in
    parser.add_argument('--reference')   # synonymous to contig
    parser.add_argument('--quality_threshold', default=15, type=int)

    # Subcommand 1: frag-coverage
    parser_command1 = subparsers.add_parser(prog='frag-converage',
                                            description='Calculates fragmentation coverage over a region given a CRAM/BAM/SAM file')
    parser_command1.add_argument('--start', type=int)   # inclusive location of region start in 0-based coordinate system. If not included, will start at the beginning of the chromosome
    parser_command1.add_argument('--stop', type=int)   # exclusive location of region end in 0-based coordinate system. If not included, will end at the end of the chromosome
    parser_command1.add_argument('--region')   # samtools region string
    parser_command1.add_argument('--method', default="frag-center")
    # parser_command1.add_argument('--quality_threshold', default=15, type=int)   # minimum phred score for a base to be counted TODO: implement threshold
    # parser_command1.add_argument('--read_callback', default='all')    # TODO: implement read callback
    parser_command1.add_argument('-v', '--verbose', default=False, type=bool)    # TODO: add verbose mode
    
    # Subcommand 2: frag-length
    parser_command2 = subparsers.add_parser(prog='frag-length',
                                            description='Calculates fragment lengths given a CRAM/BAM/SAM file')
    
    # Subcommand 2: wps()
    parser_command3 = subparsers.add_parser(prog='frag-length',
                                            description='Calculates Windowed Protection Score over a region given a CRAM/BAM/SAM file')
    parser_command3.add_argument('--start', type=int)   # inclusive location of region start in 0-based coordinate system. If not included, will start at the beginning of the chromosome
    parser_command3.add_argument('--stop', type=int)   # exclusive location of region end in 0-based coordinate system. If not included, will end at the end of the chromosome
    parser_command3.add_argument('--region')   # samtools region string


    args = parser.parse_args()
    print(frag_center_coverage(**vars(args)))


