####
# title: metadata.py
#
# language: Python3.8
# date: 2020-07-00
# license: GPL>=v3
# author: Jenny, bue
#
# description:
#   python3 library using python bioformats to extract image metadata
####


# libraries
import argparse
import bioformats  # bue20201103: can maye be replaced by tiffle, aicsimageio, or apeer-ometiff-library (mpimage)
import javabridge # bue20201103: can maye be replaced by tiffle, aicsimageio, or apeer-ometiff-library (mpimage)
from itertools import compress
import os
import pandas as pd
import re


# functions
def filename_dataframe(s_end='.czi', s_start='R'):
    '''
    version: 2020-11-10

    input:
        s_end: string at end of filenames
        s_start: string at beginning of filenames

    output:
        df_img: empty dataframe with filenames as index.

    descrition:
        get a dataframe whit filenames as index,
        that fit the choosen start end pattern as index.
    '''
    es_img = set()
    for s_file in os.listdir():
        if s_file.startswith(s_start) and s_file.endswith(s_end):
            es_img.add(s_file)
    df_img = pd.DataFrame(index=sorted(es_img))
    return(df_img)


def parse_czi(s_czidir, s_czitype='r'):
    '''
    version: 2021-03-06

    input:
        s_czidir: directory path.
        s_czitype: 'r' for regular, 's' for stitched

    output:
        df_img: dataframe with informative columns extracted form a standardisized file name.

    description:
        parse_czi is written along to koei's file naming convention:
        + the batch id is the folder:  cmif_YYYY-MM-DD_landmark
          the landmark can be a project name or a major sample something.
        the file names are like this:
        + round_markerchannel2.markerchannel3.markerchannel4.markerchannel5_slide_YYYY_MM_DD__hh_mm__scanid[-rescann]-Scene-n.czi
        + marker channel 1: always DAPI
        + slide : can contain dashes but no underscores!
        + scan id:  -scanid- or -scanid-rescan- both is possible
        the function get filenames for the requested path and extract sudden information.
    '''
    # change directory
    s_cwd = os.getcwd()
    os.chdir(s_czidir)

    # processing
    df_img = filename_dataframe(s_end='.czi', s_start='R')
    if s_czitype == 'r':  # regular
        df_img['slide'] = [s_item[2] for s_item in [s_item.split('_') for s_item in df_img.index]]
    elif s_czitype == 's':  # stitched
        df_img['slide'] = [s_item[5] for s_item in [s_item.split('_') for s_item in df_img.index]]
    else:
        sys.exit('Error @ parse_czi : unknowen s_czitype {s_czitype}.\nknowen are: r (regular) and s (stitched)')
    df_img['rounds'] = [s_item[0] for s_item in [s_item.split('_') for s_item in df_img.index]]
    df_img['markers'] = [s_item[1] for s_item in [s_item.split('_') for s_item in df_img.index]]

    # contain all filename scenes?
    b_scenes = True
    for s_item in df_img.index:
        if (s_item.find('-Scene-') < 0):
            b_scenes = False
            break
    if b_scenes:
        df_img['scene'] = [s_item[1].split('.')[0] for s_item in [s_item.split('Scene-') for s_item in df_img.index]]
        df_img['scanID'] = [s_item[-1].split('-Scene')[0] for s_item in [s_item.split('__') for s_item in df_img.index]]

    # change directory back
    os.chdir(s_cwd)
    return(df_img)


def exposure_times_image(s_image, s_find="Information\|Image\|Channel\|ExposureTime\<\/Key\>\<Value\>"): # ok
    '''
    version: 2021-03-06
    input:
        s_image: path and filename to image
        s_find: string to parse and extract the exposure time metadata
    
    output:
        li_exposure: list of each channels exposer time values in milisecond.
        s_meta: all bioformats metadata form this image stored as string.

    description:
        function to extract from a bioformat compatible image
        for each channel the exposter time in milliseconds.
    '''
    print(f'process image: {s_image} ...')
    # get bioformats metadata
    #javabridge.start_vm(class_path=bioformats.JARS)
    s_meta = bioformats.get_omexml_metadata(path=s_image)
    #o = bioformats.OMEXML(s_meta)
    #javabridge.kill_vm()
    #print(o.image().Name)
    #print(o.image().AcquisitionDate)

    # sain check
    li_start = [m.start() for m in re.finditer(s_find, s_meta)]
    if len(li_start)!=1:
        print('Error @ metadata.exposure_times_image : found wrong number of exposure times')

    # extract exposure time
    ls_exposure = []
    for i_start in li_start:
        ls_exposure.append(s_meta[i_start:i_start+200])
    s_exposure =  ls_exposure[0].strip(s_find)
    s_exposure = s_exposure[1:s_exposure.find(']')]
    ls_exposure = s_exposure.split(',')
    li_exposure = [int(s_item)/1000000 for s_item in ls_exposure]

    # output
    return(li_exposure, s_meta)


def exposure_times_slide(df_img, s_czidir='./', s_codedir=',/'):
    '''
    version: 2021-03-06
    input:
        df_img: dataframe retrieved with cmif.parse_czi function.
        s_czidir: sampleset main directory under which the czi files are located.
        s_codedir: exposer time csv file output directory.
    
    output:
        csv file with exposure time image metadata information.

    description:
        function which calles for one scene per slide, 
        for each round (there is one image per round)
        the exposure_times_image function, 
        gathers the results and writes them to a csv file.
    '''
    # slide with more then one scene
    if len(df_img.scene.unique()) > 1:
        # get a secound scene czi file from all of the czi files
        s_czifile = sorted(compress(
            os.listdir(s_czidir),
            [item.endswith('.czi') for item in os.listdir(s_czidir)]
        ))[1]
        # get scene
        s_scene = s_czifile.split('-Scene-')[1].split('.czi')[0] 

    # export exposure time
    for s_slide in sorted(set(df_img.slide)):
        print(f'\nprocess slide: {s_slide} ...')

        # slide with a single scene
        if len(df_img.scene.unique()) == 1:
            df_img_slide = df_img[df_img.slide==s_slide]
        # slide with more then one scene
        else:
            df_img_slide = df_img[(df_img.slide==s_slide) & (df_img.scene==s_scene)]

        # for each slide
        for s_slide in sorted(set(df_img_slide.slide)):
            df_exposure = pd.DataFrame()
            df_slide = df_img_slide[df_img_slide.index.str.contains(s_slide)]

            # for each image get exposure time
            for s_image in df_slide.index:
                print(s_image)
                li_exposure, s_meta = exposure_times_image(f'{s_czidir}{s_image}')
                se_times = pd.Series(li_exposure, name=s_image)
                df_exposure = df_exposure.append(se_times)

            # write image exposer time per slide dataframe to file
            s_opathfile = f'{s_codedir}/{s_slide}_jinxExposureTimes.csv'
            df_exposure.to_csv(s_opathfile,header=True,index=True)
            print(f'write file: {s_opathfile}')


def exposure_times_sampleset(ls_slide, s_codedir='./', s_czidir='./', s_czitype='r'):
    '''
    version: 2021-03-06
    input:
        ls_slide: list of slide labels to fetch exposer time.
        s_codedir: exposer time csv file output directory.
        s_czidir: sampleset main directory under which the czi files are located.
        s_czitype: type of teh czi image from which exposure time metadata is extarcted.
            usualy thise are r (regular) images, but it could be s (stitched) images too.  
   
    output:
        none

    description:
        sampleset wraper function that calls for each slide the exposure_times_slide function.
        this function will keep you sain, because when python is fired up, 
        the javabridge can only be started once before python is re-started again. 
        java and oracel sucks.
        + https://github.com/LeeKamentsky/python-javabridge/issues/88
        + https://bugs.java.com/bugdatabase/view_bug.do?bug_id=4712793
    '''
    # for each slide
    for s_slide  in ls_slide:
        # pars for czi files
        df_img = parse_czi(
            s_czidir = f'{s_czidir}{s_slide}/splitscenes/',
            s_czitype=s_czitype,  # exposer time is always taken from regular images
        )
        # slide with one or many scenes
        exposure_times_slide(
            df_img=df_img, 
            s_codedir=s_codedir, 
            s_czidir=f'{s_czidir}{s_slide}/splitscenes/', 
        )
        

# run from the command line
if __name__ == '__main__':

    # specify command line argument
    parser = argparse.ArgumentParser(description='run mplex_image.exposure_times_sampleset.')
    parser.add_argument(
        'slide', 
        help='one or more slide indetifier',
        type=str,
        nargs='+',
    )
    parser.add_argument(
        '-i',
        '--czidir', 
        help='path to czi inputfile',
        default='./',
        type=str,
    )
    parser.add_argument(
        '-o',
        '--codedir', 
        help='path to write output file (default ./)',
        default='./',
        type=str,
    )
    args = parser.parse_args()
    print('ls_slide:', args.slide)
    print('s_codedir:', args.codedir)
    print('s_czidir:', args.czidir)

    # run code
    javabridge.start_vm(class_path=bioformats.JARS)
    exposure_times_sampleset(
        ls_slide = args.slide, 
        s_codedir = args.codedir, 
        s_czidir = args.czidir, 
        s_czitype='r', 
    )    
    javabridge.kill_vm()

