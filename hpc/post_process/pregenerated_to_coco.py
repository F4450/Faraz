import os
import shutil
import zipfile
import glob
import logging
import torch
import json
import typing
from PIL import Image
from multiprocessing import Pool
from coco_to_figure_boundaries import coco_to_fig_boundaries
from figure_boundaries_train_test_split import split_train_test

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename=os.path.basename(__file__).split('.')[0] + '.log')
logger = logging.getLogger(os.path.basename(__file__))
logger.setLevel(logging.DEBUG)

# job_output_directory = '/home/sampanna/deepfigures-results/pregenerated_training_data'
job_output_directory = '/home/sampanna/deepfigures-results/372902_temp'
dataset_dir = '/home/sampanna/deepfigures-results/arxiv_coco_dataset'
image_save_dir = os.path.join(dataset_dir, 'images')
annotation_save_path = os.path.join(dataset_dir, 'annotations.json')
figure_boundaries_save_path = os.path.join(dataset_dir, 'figure_boundaries.json')
figure_boundaries_train_save_path = os.path.join(dataset_dir, 'figure_boundaries_train.json')
figure_boundaries_test_save_path = os.path.join(dataset_dir, 'figure_boundaries_test.json')
test_split_percent = 20
tmp_extract_dir = os.path.join(dataset_dir, 'tmp')


def build_annotation(bb, annotation_id: int, image_id: int, category_id: int):
    """
    Sample annotation:
    {
        "segmentation": [
          [510.66,423.01,511.72,420.03,510.45,416,510.45,423.01]
        ],
        "area": 702.1057499999998,
        "iscrowd": 0,
        "image_id": 289343,
        "bbox": [
          473.07,
          395.93,
          38.65,
          28.67
        ],
        "category_id": 18,
        "id": 1768
    }
    """
    x1, y1, x2, y2 = bb[1].item(), bb[3].item(), bb[2].item(), bb[4].item()
    top_left = (x1, y1)
    width = x2 - x1
    height = y2 - y1
    return {
        "id": annotation_id,
        "image_id": image_id,
        "category_id": category_id,
        "segmentation": [[x1, y1, x2, y1, x2, y2, x1, y2]],
        "area": width * height,
        "bbox": [top_left[0], top_left[1], width, height],
        "iscrowd": 0
    }


def build_image(image_path: str, image_id: int, height: int, width: int):
    """
    Sample image:
    {
        "license": 4,
        "file_name": "000000397133.jpg",
        "coco_url": "http://images.cocodataset.org/val2017/000000397133.jpg",
        "height": 427,
        "width": 640,
        "date_captured": "2013-11-14 17:02:52",
        "flickr_url": "http://farm7.staticflickr.com/6116/6255196340_da26cf2c9e_z.jpg",
        "id": 397133
    }
    """
    return {
        "license": 2,  # TODO: Confirm this.
        "file_name": os.path.basename(image_path),
        "coco_url": "",
        "height": height,
        "width": width,
        "date_captured": "2020-05-20 01:00:00",
        "flickr_url": "",
        "id": image_id
    }


def unzip_zip_file(zip_file_path: str, extract_dir: str = tmp_extract_dir) -> typing.Tuple[
    typing.List[str], typing.List[str]]:
    """
    Takes in a zip file path. Unzips it in a temporary directory. And returns the list of the files unzipped.
    Works only for flat file-structured zips.
    :param zip_file_path: path os the zip file.
    :param extract_dir: The directory to extract the data into.
    :return: the list of path of the contents of the zip (all, png and pt)
    """
    process_unzip_dir = os.path.join(extract_dir, str(os.getpid()))
    os.makedirs(process_unzip_dir, exist_ok=True)
    zip = zipfile.ZipFile(zip_file_path)
    zip.extractall(path=process_unzip_dir)
    zip.close()
    file_list = os.listdir(os.path.join(process_unzip_dir, 'tmp'))
    png_paths = [os.path.join(process_unzip_dir, 'tmp', path) for path in file_list if '.png' in path]
    pt_paths = [os.path.join(process_unzip_dir, 'tmp', path) for path in file_list if '.pt' in path]
    assert len(png_paths) == len(pt_paths)
    return png_paths, pt_paths


os.makedirs(dataset_dir, exist_ok=True)
os.makedirs(image_save_dir, exist_ok=True)
shutil.rmtree(tmp_extract_dir, ignore_errors=True)
os.makedirs(tmp_extract_dir, exist_ok=True)

if os.path.exists(annotation_save_path):
    dataset = json.load(open(annotation_save_path))
else:
    dataset = json.load(open('coco_dataset_template.json'))

current_image_id = max([image['id'] for image in dataset['images']], default=0) + 1
current_annotation_id = max([annotation['id'] for annotation in dataset['annotations']], default=0) + 1

zip_paths = glob.glob(os.path.join(job_output_directory, '*/*.zip'), recursive=True)
batch_size = 7
batches = [zip_paths[i:i + batch_size] for i in range(0, len(zip_paths), batch_size)]
for batch in batches:
    p = Pool(batch_size)
    result_list = p.map(unzip_zip_file, batch)
    png_paths = []
    pt_paths = []
    for result_tuple in result_list:
        png_paths = png_paths + result_tuple[0]
        pt_paths = pt_paths + result_tuple[1]

    for idx, png_path in enumerate(png_paths):
        pt_path = pt_paths[idx]
        logger.info("Idx: {}, Png path: {}, pt path: {}.".format(idx, png_path, pt_path))
        if png_path.split('.png')[0] != pt_path.split('.pt')[0]:
            logger.warning("Found an instance when the pt path is not the same as png path. Skipping")
            logger.warning("pt path: {}. Png path: {}".format(pt_path, png_path))
            continue

        _image_save_path = os.path.join(image_save_dir, str(current_image_id) + '.png')
        os.rename(png_path, _image_save_path)
        img = Image.open(_image_save_path)
        image_json = build_image(image_path=_image_save_path, image_id=current_image_id, height=img.size[0],
                                 width=img.size[1])
        dataset['images'].append(image_json)

        tensor = torch.load(pt_path)
        for bb in tensor:
            annotation_json = build_annotation(bb=bb, annotation_id=current_annotation_id, image_id=current_image_id,
                                               category_id=1)
            dataset['annotations'].append(annotation_json)
            current_annotation_id = current_annotation_id + 1
        current_image_id = current_image_id + 1

    # Cleanup the temp directory.
    shutil.rmtree(tmp_extract_dir, ignore_errors=True)
    os.makedirs(tmp_extract_dir, exist_ok=True)
    # checkpoint the annotation file.
    json.dump(dataset, open(annotation_save_path, mode='w'), indent=2)
    logger.info("Successfully saved annotations after processing zipfile batch paths: {}".format(batch))
    logger.info("Current image id: {}, current annotation id: {}".format(current_image_id, current_annotation_id))

# coco_to_fig_boundaries(coco_annotation_file=annotation_save_path,
#                        figure_boundaries_save_path=figure_boundaries_save_path)
# split_train_test(figure_boundaries_path=figure_boundaries_save_path,
#                  train_output_path=figure_boundaries_train_save_path,
#                  test_output_path=figure_boundaries_test_save_path, test_split_percent=test_split_percent)