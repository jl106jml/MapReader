#!/usr/bin/env python
# -*- coding: utf-8 -*-

import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import random
import requests
import sys
import yaml

from mapreader import loader, load_patches

from ipyannotate.toolbar import Toolbar
from ipyannotate.tasks import Task, Tasks
from ipyannotate.canvas import OutputCanvas
from ipyannotate.annotation import Annotation
from ipyannotate.buttons import (
    ValueButton as Button,
    NextButton as Next,
    BackButton as Back,
)

from PIL import Image
from typing import List, Optional, Union, Dict, Tuple


def display_record(record: Tuple[str, str, str, int, int]) -> None:
    """
    Displays an image and optionally, a context image with a patch border.

    Parameters
    ----------
    record : tuple
        A tuple containing the following elements:
            - str : The name of the patch.
            - str : The path to the image to be displayed.
            - str : The path to the parent image, if any.
            - int : The index of the task, if any.
            - int : The number of times this patch has been displayed.

    Returns
    -------
    None

    Notes
    -----
    This function should be called from ``prepare_annotation``, there are
    several global variables that are being set in the function.

    This function uses ``matplotlib`` to display images. If the context image
    is displayed, the border of the patch is highlighted in red.

    Refer to ``ipyannotate`` and ``matplotlib`` for more info.
    """

    # setup the images
    gridsize = (5, 1)
    plt.clf()
    plt.figure(figsize=(12, 12))
    if treelevel == "patch" and contextimage:
        plt.subplot2grid(gridsize, (2, 0))
    else:
        plt.subplot2grid(gridsize, (0, 0), rowspan=2)
    plt.imshow(Image.open(record[1]))
    plt.xticks([])
    plt.yticks([])
    plt.title(f"{record[0]}", size=20)

    if treelevel == "patch" and contextimage:
        parent_path = os.path.dirname(
            annotation_tasks["paths"][record[3]]["parent_paths"]
        )
        # Here, we assume that min_x, min_y, max_x and max_y are in the patch
        # name
        split_path = record[0].split("-")
        min_x, min_y, max_x, max_y = (
            int(split_path[1]),
            int(split_path[2]),
            int(split_path[3]),
            int(split_path[4]),
        )

        # context image
        plt.subplot2grid(gridsize, (0, 0), rowspan=2)

        # ---
        path = os.path.join(parent_path, record[2])
        par_img = Image.open(path).convert("RGB")
        min_y_par = max(0, min_y - y_offset)
        min_x_par = max(0, min_x - x_offset)
        max_x_par = min(max_x + x_offset, np.shape(par_img)[1])
        max_y_par = min(max_y + y_offset, np.shape(par_img)[0])

        # par_img = par_img[min_y_par:max_y_par, min_x_par:max_x_par]
        par_img = par_img.crop((min_x_par, min_y_par, max_x_par, max_y_par))

        plt.imshow(par_img, extent=(min_x_par, max_x_par, max_y_par, min_y_par))
        # ---

        plt.xticks([])
        plt.yticks([])

        # plot the patch border on the context image
        plt.plot([min_x, min_x], [min_y, max_y], lw=2, zorder=10, color="r")
        plt.plot([min_x, max_x], [min_y, min_y], lw=2, zorder=10, color="r")
        plt.plot([max_x, max_x], [max_y, min_y], lw=2, zorder=10, color="r")
        plt.plot([max_x, min_x], [max_y, max_y], lw=2, zorder=10, color="r")

        """
        # context image
        plt.subplot2grid(gridsize, (3, 0), rowspan=2)
        min_y_par = 0
        min_x_par = 0
        max_x_par = par_img.shape[1]
        max_y_par = par_img.shape[0]
        plt.imshow(par_img[min_y_par:max_y_par, min_x_par:max_x_par],
                    extent=(min_x_par, max_x_par, max_y_par, min_y_par))
        plt.plot([min_x_par, min_x_par],
                    [min_y_par, max_y_par],
                    lw=2, zorder=10, color="k")
        plt.plot([min_x_par, max_x_par],
                    [min_y_par, min_y_par],
                    lw=2, zorder=10, color="k")
        plt.plot([max_x_par, max_x_par],
                    [max_y_par, min_y_par],
                    lw=2, zorder=10, color="k")
        plt.plot([max_x_par, min_x_par],
                    [max_y_par, max_y_par],
                    lw=2, zorder=10, color="k")

        plt.xticks([])
        plt.yticks([])

        # plot the patch border on the context image
        plt.plot([min_x, min_x],
                    [min_y, max_y],
                    lw=2, zorder=10, color="r")
        plt.plot([min_x, max_x],
                    [min_y, min_y],
                    lw=2, zorder=10, color="r")
        plt.plot([max_x, max_x],
                    [max_y, min_y],
                    lw=2, zorder=10, color="r")
        plt.plot([max_x, min_x],
                    [max_y, max_y],
                    lw=2, zorder=10, color="r")
        """

    plt.tight_layout()
    plt.show()

    print(20 * "-")
    print("Additional info:")
    print(f"Counter: {record[-1]}")
    if url_main:
        try:
            map_id = record[2].split("_")[-1].split(".")[0]
            url = f"{url_main}/{map_id}"
            # stream=True so we don't download the whole page, only check if
            # the page exists
            response = requests.get(url, stream=True)
            assert response.status_code < 400
            print()
            print(f"URL: {url}")
        except:
            url = False
            pass


def prepare_data(
    df: pd.DataFrame,
    col_names: Optional[List[str]] = ["image_path", "parent_id"],
    annotation_set: Optional[str] = "001",
    label_col_name: Optional[str] = "label",
    redo: Optional[bool] = False,
    random_state: Optional[Union[int, str]] = "random",
    num_samples: Optional[int] = 100,
) -> List[List[Union[str, int]]]:
    """
    Prepare data for image annotation by selecting a subset of images from a
    DataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing the image data to be annotated.
    col_names : list of str, optional
        List of column names to include in the output. Default columns are
        ``["image_path", "parent_id"]``.
    annotation_set : str, optional
        String specifying the annotation set. Default is ``"001"``.
    label_col_name : str, optional
        Column name containing the label information for each image. Default
        is ``"label"``.
    redo : bool, optional
        If ``True``, all images will be annotated even if they already have a
        label. If ``False`` (default), only images without a label will be
        annotated.
    random_state : int or str, optional
        Seed for the random number generator used when selecting images to
        annotate. If set to ``"random"`` (default), a random seed will be used.
    num_samples : int, optional
        Maximum number of images to annotate. Default is ``100``.

    Returns
    -------
    list of list of str/int
        A list of lists containing the selected image data, with each sublist
        containing the specified columns plus the annotation set and a row
        counter.
    """

    if (label_col_name in list(df.columns)) and (not redo):
        already_annotated = len(df[~df[label_col_name].isnull()])
        print(f"Number of already annotated images: {already_annotated}")
        # only annotate those patches that have not been already annotated
        df = df[df[label_col_name].isnull()]
        print(f"Number of images to be annotated (total): {len(df)}")
    else:
        # if redo = True or "label" column does not exist
        # annotate all patches in the pandas dataframe
        pass

    tar_param = "mean_pixel_RGB"
    if tar_param in df.columns:
        try:
            pd.options.mode.chained_assignment = None
            df["pixel_groups"] = pd.qcut(
                df[tar_param], q=10, precision=2, labels=False
            ).values
            if random_state in ["random"]:
                df = df.groupby("pixel_groups").sample(
                    n=10, random_state=random.randint(0, 1e6)
                )
            else:
                df = df.groupby("pixel_groups").sample(n=10, random_state=random_state)
        except Exception:
            print(f"[INFO] len(df) = {len(df)}, .sample method is deactivated.")
            df = df.iloc[:num_samples]
    else:
        print(f"[WARNING] could not find {tar_param} in columns.")
        df = df.iloc[:num_samples]

    data = []
    row_counter = 0
    for one_row in df.iterrows():
        cols2add = [one_row[0]]
        for i in col_names:
            cols2add.append(one_row[1][i])
        cols2add.append(annotation_set)
        cols2add.append(row_counter)
        data.append(cols2add)
        row_counter += 1

    print(f"Number of images to annotate (current batch): {len(data)}")
    return data


def annotation_interface(
    data: List,
    list_labels: List,
    list_colors: Optional[List[str]] = ["red", "green", "blue", "green"],
    annotation_set: Optional[str] = "001",
    method: Optional[str] = "ipyannotate",
    list_shortcuts: Optional[List[str]] = None,
) -> Annotation:
    """
    Create an annotation interface for a list of patches with corresponding
    labels.

    Parameters
    ----------
    data : list
        List of patches to annotate.
    list_labels : list
        List of strings representing the labels for each annotation class.
    list_colors : list, optional
        List of strings representing the colors for each annotation class,
        by default ``["red", "green", "blue", "green"]``.
    annotation_set : str, optional
        String representing the annotation set, specified in the yaml file or
        via function argument, by default ``"001"``.
    method : str, optional
        String representing the method for annotation, by default
        ``"ipyannotate"``.
    list_shortcuts : list, optional
        List of strings representing the keyboard shortcuts for each
        annotation class, by default ``None``.

    Returns
    -------
    annotation : Annotation
        The annotation object containing the toolbar, tasks and canvas for the
        interface.

    Raises
    ------
    SystemExit
        If ``method`` parameter is not ``"ipyannotate"``.

    Notes
    -----
    This function creates an annotation interface using the ``ipyannotate``
    library, which is a browser-based tool for annotating data.
    """

    if method == "ipyannotate":
        if not list_shortcuts:
            list_shortcuts = [
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "a",
                "b",
                "c",
                "d",
                "e",
                "f",
                "g",
                "h",
                "i",
                "l",
                "m",
                "n",
                "o",
                "p",
                "q",
                "r",
                "s",
                "t",
                "u",
                "v",
                "w",
                "x",
                "y",
                "z",
            ]
        list_colors *= 10
        canvas = OutputCanvas(display=display_record)
        # Collect all tasks
        tasks = Tasks(Task(_) for _ in data)
        buttons = []
        for i, one_label in enumerate(list_labels):
            buttons.append(
                Button(
                    i + 1,
                    label=one_label,
                    color=list_colors[i],
                    shortcut=list_shortcuts[i],
                )
            )
        controls = [Back(shortcut="j"), Next(shortcut="k")]
        toolbar = Toolbar(buttons + controls)
        annotation = Annotation(toolbar, tasks, canvas=canvas)
        return annotation

    sys.exit(
        f"method: {method} is not implemented. Currently, we support: ipyannotate"  # noqa
    )


def prepare_annotation(
    userID: str,
    task: str,
    annotation_tasks_file: str,
    custom_labels: List[str] = [],
    annotation_set: Optional[str] = "001",
    redo_annotation: Optional[bool] = False,
    patch_paths: Optional[Union[str, bool]] = False,
    parent_paths: Optional[str] = False,
    tree_level: Optional[str] = "patch",
    sortby: Optional[str] = None,
    min_alpha_channel: Optional[float] = None,
    min_mean_pixel: Optional[float] = None,
    max_mean_pixel: Optional[float] = None,
    min_std_pixel: Optional[float] = None,
    max_std_pixel: Optional[float] = None,
    context_image: Optional[bool] = False,
    xoffset: Optional[int] = 500,
    yoffset: Optional[int] = 500,
    urlmain: Optional[str] = "https://maps.nls.uk/view/",
    random_state: Optional[Union[str, int]] = "random",
    list_shortcuts: Optional[List[tuple]] = None,
) -> Dict:
    """Prepare image data for annotation and launch the annotation interface.

    Parameters
    ----------
    userID : str
        The ID of the user annotating the images. Should be unique as it is
        used in the name of the output file.
    task : str
        The task name that the images are associated with. This task should be
        defined in the yaml file (``annotation_tasks_file``), if not,
        ``custom_labels`` will be used instead.
    annotation_tasks_file : str
        The file path to the YAML file containing information about task, image
        paths and annotation metadata.
    custom_labels : list of str, optional
        A list of custom label names to be used instead of the label names in
        the ``annotation_tasks_file``. Default is ``[]``.
    annotation_set : str, optional
        The ID of the annotation set to use in the YAML file
        (``annotation_tasks_file``). Default is ``"001"``.
    redo_annotation : bool, optional
        If ``True``, allows the user to redo annotations on previously
        annotated images. Default is ``False``.
    patch_paths : str or bool, optional
        The path to the directory containing patches, if ``custom_labels`` are provided. Default is ``False`` and the information is read from the yaml file.
    parent_paths : str, optional
        The path to parent images, if ``custom_labels`` are provided. Default
        is ``False`` and the information is read from the yaml file.
    tree_level : str, optional
        The level of annotation to be used, either ``"patch"`` or ``"parent"``.
        Default is ``"patch"``.
    sortby : str, optional
        If ``"mean"``, sort images by mean pixel intensity. Default is
        ``None``.
    min_alpha_channel : float, optional
        The minimum alpha channel value for images to be included in the
        annotation interface. Only applies to patch level annotations.
        Default is ``None``.
    min_mean_pixel : float, optional
        The minimum mean pixel intensity value for images to be included in
        the annotation interface. Only applies to patch level annotations.
        Default is ``None``.
    max_mean_pixel : float, optional
        The maximum mean pixel intensity value for images to be included in
        the annotation interface. Only applies to patch level annotations.
        Default is ``None``.
    min_std_pixel : float, optional
        The minimum standard deviation of pixel intensity value for images to be included in
        the annotation interface. Only applies to patch level annotations.
        Default is ``None``.
    max_std_pixel : float, optional
        The maximum standard deviation of pixel intensity value for images to be included in
        the annotation interface. Only applies to patch level annotations.
        Default is ``None``.
    context_image : bool, optional
        If ``True``, includes a context image with each patch image in the
        annotation interface. Only applies to patch level annotations. Default
        is ``False``.
    xoffset : int, optional
        The x-offset in pixels to be used for displaying context images in the
        annotation interface. Default is ``500``.
    yoffset : int, optional
        The y-offset in pixels to be used for displaying context images in the
        annotation interface. Default is ``500``.
    urlmain : str, optional
        The main URL to be used for displaying images in the annotation
        interface. Default is ``"https://maps.nls.uk/view/"``.
    random_state : int or str, optional
        Seed or state value for the random number generator used for shuffling
        the image order. Default is ``"random"``.
    list_shortcuts : list of tuples, optional
        A list of tuples containing shortcut key assignments for label names.
        Default is ``None``.

    Returns
    -------
    annotation : dict
        A dictionary containing the annotation results.

    Raises
    -------
    ValueError
        If a specified annotation_set is not a key in the paths dictionary
        of the YAML file with the information about the annotation metadata
        (``annotation_tasks_file``).
    """

    # Specify global variables so they can be used in display_record function
    global annotation_tasks
    global x_offset
    global y_offset
    global url_main
    global treelevel
    global contextimage

    # Note: it is not possible to define global variable + args with the same
    # names so here, we read xoffset and yoffset, assign them to two global
    # variables as these global variables will then be used in display_record
    x_offset = xoffset
    y_offset = yoffset
    url_main = urlmain
    treelevel = tree_level
    contextimage = context_image

    with open(annotation_tasks_file) as annot_file_fio:
        annotation_tasks = yaml.load(annot_file_fio, Loader=yaml.FullLoader)

    if annotation_set not in annotation_tasks["paths"].keys():
        raise ValueError(
            f"{annotation_set} could not be found in {annotation_tasks_file}"
        )
    else:
        if tree_level == "patch":
            patch_paths = annotation_tasks["paths"][annotation_set]["patch_paths"]
        parent_paths = os.path.join(
            annotation_tasks["paths"][annotation_set]["parent_paths"]
        )
        annot_file = os.path.join(
            annotation_tasks["paths"][annotation_set]["annot_dir"],
            f"{task}_#{userID}#.csv",
        )

    if task not in annotation_tasks["tasks"].keys():
        if custom_labels == []:
            raise ValueError(
                f"Task: {task} could not be found and custom_labels == []."
            )
        list_labels = custom_labels
    else:
        list_labels = annotation_tasks["tasks"][task]["labels"]

    if tree_level == "patch":
        # specify the path of patches and the parent images
        mymaps = load_patches(patch_paths=patch_paths, parent_paths=parent_paths)
        if os.path.isfile(annot_file):
            mymaps.add_metadata(
                metadata=annot_file,
                index_col=-1,
                delimiter=",",
                tree_level=tree_level,
            )

        calc_mean = calc_std = False
        # Calculate mean before converting to pandas so the dataframe contains information about mean pixel intensity
        if (
            sortby == "mean"
            or isinstance(min_alpha_channel, float)
            or isinstance(min_mean_pixel, float)
            or isinstance(max_mean_pixel, float)
        ):
            calc_mean = True

        if isinstance(min_std_pixel, float) or isinstance(max_std_pixel, float):
            calc_std = True

        if calc_mean or calc_std:
            mymaps.calc_pixel_stats(calc_mean=calc_mean, calc_std=calc_std)

        # convert images to dataframe
        _, patch_df = mymaps.convertImages()

        if sortby == "mean":
            patch_df.sort_values("mean_pixel_RGB", inplace=True)

        if isinstance(min_alpha_channel, float):
            if "mean_pixel_A" in patch_df.columns:
                patch_df = patch_df[patch_df["mean_pixel_A"] >= min_alpha_channel]

        if isinstance(min_mean_pixel, float):
            if "mean_pixel_RGB" in patch_df.columns:
                patch_df = patch_df[patch_df["mean_pixel_RGB"] >= min_mean_pixel]

        if isinstance(max_mean_pixel, float):
            if "mean_pixel_RGB" in patch_df.columns:
                patch_df = patch_df[patch_df["mean_pixel_RGB"] <= max_mean_pixel]

        if isinstance(min_std_pixel, float):
            if "std_pixel_RGB" in patch_df.columns:
                patch_df = patch_df[patch_df["std_pixel_RGB"] >= min_std_pixel]

        if isinstance(max_std_pixel, float):
            if "std_pixel_RGB" in patch_df.columns:
                patch_df = patch_df[patch_df["std_pixel_RGB"] <= max_std_pixel]

        if isinstance(min_std_pixel, float):
            if "std_pixel_RGB" in patch_df.columns:
                patch_df = patch_df[patch_df["std_pixel_RGB"] >= min_std_pixel]

        if isinstance(max_std_pixel, float):
            if "std_pixel_RGB" in patch_df.columns:
                patch_df = patch_df[patch_df["std_pixel_RGB"] <= max_std_pixel]

        col_names = ["image_path", "parent_id"]
    else:
        mymaps = loader(path_images=parent_paths)
        if os.path.isfile(annot_file):
            mymaps.add_metadata(
                metadata=annot_file,
                index_col=-1,
                delimiter=",",
                tree_level=tree_level,
            )
        # convert images to dataframe
        patch_df, _ = mymaps.convertImages()
        col_names = ["image_path"]

    # prepare data for annotation
    data2annotate = prepare_data(
        patch_df,
        col_names=col_names,
        annotation_set=annotation_set,
        redo=redo_annotation,
        random_state=random_state,
    )

    if len(data2annotate) == 0:
        print("No image to annotate!")
    else:
        annotation = annotation_interface(
            data2annotate,
            list_labels=list_labels,
            annotation_set=annotation_set,
            list_shortcuts=list_shortcuts,
        )
        return annotation


def save_annotation(
    annotation: Annotation,
    userID: str,
    task: str,
    annotation_tasks_file: str,
    annotation_set: str,
) -> None:
    """
    Save annotations for a given task and user to a csv file.

    Parameters
    ----------
    annotation : ipyannotate.annotation.Annotation
        Annotation object containing the annotations to be saved (output from
        the annotation tool).
    userID : str
        User ID of the person performing the annotation. This should be unique
        as it is used in the name of the output file.
    task : str
        Name of the task being annotated.
    annotation_tasks_file : str
        Path to the yaml file describing the annotation tasks, paths, etc.
    annotation_set : str
        Name of the annotation set to which the annotations belong, defined in
        the ``annotation_tasks_file``.

    Returns
    -------
    None
    """
    with open(annotation_tasks_file) as f:
        annotation_tasks = yaml.load(f, Loader=yaml.FullLoader)

    if annotation_set not in annotation_tasks["paths"].keys():
        print(f"{annotation_set} could not be found in {annotation_tasks_file}")
    else:
        annot_file = os.path.join(
            annotation_tasks["paths"][annotation_set]["annot_dir"],
            f"{task}_#{userID}#.csv",
        )

    annot_file_par = os.path.dirname(os.path.abspath(annot_file))
    if not os.path.isdir(annot_file_par):
        os.makedirs(annot_file_par)

    # Read an existing annotation file (for the same task and userID)
    try:
        image_df = pd.read_csv(annot_file)
    except:
        image_df = pd.DataFrame(columns=["image_id", "label"])

    new_labels = 0
    newly_annotated = 0
    for i in range(len(annotation.tasks)):
        if annotation.tasks[i].value is not None:
            newly_annotated += 1
            if (
                not annotation.tasks[i].output[0]
                in image_df["image_id"].values.tolist()
            ):
                image_df = image_df.append(
                    {
                        "image_id": annotation.tasks[i].output[0],
                        "label": annotation.tasks[i].value,
                    },
                    ignore_index=True,
                )
                new_labels += 1

    if len(image_df) > 0:
        image_df = image_df.set_index("image_id")
        image_df.to_csv(annot_file, mode="w")
        print(f"[INFO] Save {newly_annotated} new annotations to {annot_file}")
        print(f"[INFO] {new_labels} labels were not already stored")
        print(f"[INFO] Total number of annotations: {len(image_df)}")
    else:
        print("[INFO] No annotations to save!")
