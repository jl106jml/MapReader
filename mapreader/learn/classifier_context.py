#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .classifier import classifier

import copy
import matplotlib.pyplot as plt
import numpy as np
import os
import time
import torchvision

# from tqdm.autonotebook import tqdm
from typing import Union, List, Optional, Tuple, Dict

import torch


class classifierContext(classifier):
    def train(
        self,
        phases: Optional[List[str]] = ["train", "val"],
        num_epochs: Optional[int] = 25,
        save_model_dir: Optional[Union[str, None]] = "models",
        verbosity_level: Optional[int] = 1,
        tensorboard_path: Optional[Union[str, None]] = None,
        tmp_file_save_freq: Optional[Union[int, None]] = 2,
        remove_after_load: Optional[bool] = True,
        print_info_batch_freq: Optional[Union[int, None]] = 5,
    ) -> None:
        """
        Train the model on the specified phases for a given number of epochs.
        Wrapper function for ``train_core`` method to capture exceptions (with
        supported exceptions so far: ``KeyboardInterrupt``). Refer to
        ``train_core`` for more information.

        Parameters
        ----------
        phases : list of str, optional
            The phases to train the model on for each epoch. Default is
            ``["train", "val"]``.
        num_epochs : int, optional
            The number of epochs to train the model for. Default is ``25``.
        save_model_dir : str or None, optional
            The directory to save the model in. Default is ``"models"``. If
            set to ``None``, the model is not saved.
        verbosity_level : int, optional
            The level of verbosity during training:

            - ``0`` is silent,
            - ``1`` is progress bar and metrics,
            - ``2`` is detailed information.

            Default is ``1``.
        tensorboard_path : str or None, optional
            The path to the directory to save TensorBoard logs in. If set to
            ``None``, no TensorBoard logs are saved. Default is ``None``.
        tmp_file_save_freq : int, optional
            The frequency (in epochs) to save a temporary file of the model.
            Default is ``2``. If set to ``0`` or ``None``, no temporary file
            is saved.
        remove_after_load : bool, optional
            Whether to remove the temporary file after loading it. Default is
            ``True``.
        print_info_batch_freq : int, optional
            The frequency (in batches) to print training information. Default
            is ``5``. If set to ``0`` or ``None``, no training information is
            printed.

        Returns
        -------
        None
            The function saves the model to the ``save_model_dir`` directory,
            and optionally to a temporary file. If interrupted with a
            ``KeyboardInterrupt``, the function tries to load the temporary
            file. If no temporary file is found, it continues without loading.
        """

        try:
            self.train_core(
                phases,
                num_epochs,
                save_model_dir,
                verbosity_level,
                tensorboard_path,
                tmp_file_save_freq,
                print_info_batch_freq=print_info_batch_freq,
            )
        except KeyboardInterrupt:
            print("KeyboardInterrupted... Exiting...")
            if os.path.isfile(self.tmp_save_filename):
                print(f"File found: {self.tmp_save_filename}... Loading...")
                self.load(self.tmp_save_filename, remove_after_load=remove_after_load)
            else:
                print("No temporary file was found.")

    def train_core(
        self,
        phases: Optional[List[str]] = ["train", "val"],
        num_epochs: Optional[int] = 25,
        save_model_dir: Optional[Union[str, None]] = "models",
        verbosity_level: Optional[int] = 1,
        tensorboard_path: Optional[Union[str, None]] = None,
        tmp_file_save_freq: Optional[Union[int, None]] = 2,
        print_info_batch_freq: Optional[Union[int, None]] = 5,
    ) -> None:
        """
        Trains/fine-tunes a classifier for the specified number of epochs on
        the given phases using the specified hyperparameters.

        Parameters
        ----------
        phases : list of str, optional
            The phases to train the model on for each epoch. Default is
            ``["train", "val"]``.
        num_epochs : int, optional
            The number of epochs to train the model for. Default is ``25``.
        save_model_dir : str or None, optional
            The directory to save the model in. Default is ``"models"``. If
            set to ``None``, the model is not saved.
        verbosity_level : int, optional
            The level of verbosity during training:

            - ``0`` is silent,
            - ``1`` is progress bar and metrics,
            - ``2`` is detailed information.

            Default is ``1``.
        tensorboard_path : str or None, optional
            The path to the directory to save TensorBoard logs in. If set to
            ``None``, no TensorBoard logs are saved. Default is ``None``.
        tmp_file_save_freq : int, optional
            The frequency (in epochs) to save a temporary file of the model.
            Default is ``2``. If set to ``0`` or ``None``, no temporary file
            is saved.
        print_info_batch_freq : int, optional
            The frequency (in batches) to print training information. Default
            is ``5``. If set to ``0`` or ``None``, no training information is
            printed.

        Raises
        ------
        ValueError
            If the criterion is not set. Use the ``add_criterion`` method to
            set the criterion.

            If the optimizer is not set and the phase is "train". Use the
            ``initialize_optimizer`` or ``add_optimizer`` method to set the
            optimizer.

        KeyError
            If the specified phase cannot be found in the object's dataloader
            with keys.

        Returns
        -------
        None
        """

        if self.criterion is None:
            raise ValueError("[ERROR] criterion is needed. Use add_criterion method")

        for phase in phases:
            if phase not in self.dataloader.keys():
                raise KeyError(
                    f"[ERROR] specified phase: {phase} cannot be find in object's dataloader with keys: {self.dataloader.keys()}"  # noqa
                )

        if verbosity_level >= 1:
            self.train_component_summary()

        since = time.time()

        # initialize variables
        train_phase_names = ["train", "training"]
        valid_phase_names = ["val", "validation", "eval", "evaluation"]
        best_model_wts = copy.deepcopy(self.model.state_dict())
        self.pred_conf = []
        self.pred_label = []
        self.orig_label = []
        if save_model_dir is not None:
            save_model_dir = os.path.abspath(save_model_dir)

        # Check if SummaryWriter (for tensorboard) can be imported
        tboard_writer = None
        if tensorboard_path is not None:
            try:
                from torch.utils.tensorboard import SummaryWriter

                tboard_writer = SummaryWriter(tensorboard_path)
            except ImportError:
                print(
                    "[WARNING] could not import SummaryWriter from torch.utils.tensorboard"  # noqa
                )
                print("[WARNING] continue without tensorboard.")
                tensorboard_path = None

        start_epoch = self.last_epoch + 1
        end_epoch = self.last_epoch + num_epochs

        # --- Main train loop
        for epoch in range(start_epoch, end_epoch + 1):
            # --- loop, phases
            for phase in phases:
                if phase.lower() in train_phase_names:
                    self.model.train()
                else:
                    self.model.eval()

                # initialize vars with one epoch lifetime
                running_loss = 0.0
                running_pred_conf = []
                running_pred_label = []
                running_orig_label = []

                # TQDM
                # batch_loop = tqdm(iter(self.dataloader[phase]), total=len(self.dataloader[phase]), leave=False) # noqa
                # if phase.lower() in train_phase_names+valid_phase_names:
                #     batch_loop.set_description(f"Epoch {epoch}/{end_epoch}")

                phase_batch_size = self.dataloader[phase].batch_size
                total_inp_counts = len(self.dataloader[phase].dataset)

                # --- loop, batches
                for batch_idx, (inputs1, inputs2, labels) in enumerate(
                    self.dataloader[phase]
                ):
                    inputs1 = inputs1.to(self.device)
                    inputs2 = inputs2.to(self.device)
                    labels = labels.to(self.device)

                    if self.optimizer is None:
                        if phase.lower() in train_phase_names:
                            raise ValueError(
                                f"[ERROR] optimizer should be set when phase is {phase}. Use initialize_optimizer or add_optimizer."  # noqa
                            )
                    else:
                        self.optimizer.zero_grad()

                    if phase.lower() in train_phase_names + valid_phase_names:
                        # forward, track history if only in train
                        with torch.set_grad_enabled(phase.lower() in train_phase_names):
                            # Get model outputs and calculate loss
                            # Special case for inception because in training
                            # it has an auxiliary output.
                            #     In train mode we calculate the loss by
                            #     summing the final output and the auxiliary
                            #     output but in testing we only consider the
                            #     final output.
                            if self.is_inception and (
                                phase.lower() in train_phase_names
                            ):
                                outputs, aux_outputs = self.model(inputs1, inputs2)
                                loss1 = self.criterion(outputs, labels)
                                loss2 = self.criterion(aux_outputs, labels)
                                # XXX From https://discuss.pytorch.org/t/how-to-optimize-inception-model-with-auxiliary-classifiers/7958 # noqa
                                loss = loss1 + 0.4 * loss2
                            else:
                                outputs = self.model(inputs1, inputs2)
                                # labels = labels.long().squeeze_()
                                loss = self.criterion(outputs, labels)

                            _, pred_label = torch.max(outputs, dim=1)

                            # backward + optimize only if in training phase
                            if phase.lower() in train_phase_names:
                                loss.backward()
                                self.optimizer.step()

                        # XXX (why multiply?)
                        running_loss += loss.item() * inputs1.size(0)

                        # TQDM
                        # batch_loop.set_postfix(loss=loss.data)
                        # batch_loop.refresh()
                    else:
                        outputs = self.model(inputs1, inputs2)
                        _, pred_label = torch.max(outputs, dim=1)

                    running_pred_conf.extend(
                        torch.nn.functional.softmax(outputs, dim=1).cpu().tolist()
                    )
                    running_pred_label.extend(pred_label.cpu().tolist())
                    running_orig_label.extend(labels.cpu().tolist())

                    if batch_idx % print_info_batch_freq == 0:
                        curr_inp_counts = min(
                            total_inp_counts,
                            (batch_idx + 1) * phase_batch_size,
                        )
                        progress_perc = curr_inp_counts / total_inp_counts * 100.0
                        tmp_str = f"{curr_inp_counts}/{total_inp_counts} ({progress_perc:5.1f}%)"  # noqa

                        epoch_msg = f"{phase: <8} -- {epoch}/{end_epoch} -- "
                        epoch_msg += f"{tmp_str: >20} -- "

                        if phase.lower() in valid_phase_names:
                            epoch_msg += f"Loss: {loss.data:.3f}"
                            self.cprint("[INFO]", self.color_dred, epoch_msg)
                        elif phase.lower() in train_phase_names:
                            epoch_msg += f"Loss: {loss.data:.3f}"
                            self.cprint("[INFO]", self.color_dgreen, epoch_msg)
                        else:
                            self.cprint("[INFO]", self.color_dgreen, epoch_msg)
                    # --- END: one batch

                # scheduler
                if phase.lower() in train_phase_names and (self.scheduler is not None):
                    self.scheduler.step()

                if phase.lower() in train_phase_names + valid_phase_names:
                    # --- collect statistics
                    epoch_loss = running_loss / self.dataset_sizes[phase]
                    self._add_metrics(f"epoch_loss_{phase}", epoch_loss)

                    if tboard_writer is not None:
                        tboard_writer.add_scalar(
                            f"loss/{phase}",
                            self.metrics[f"epoch_loss_{phase}"][-1],
                            epoch,
                        )

                    # other metrics (precision/recall/F1)
                    self.calculate_add_metrics(
                        running_orig_label,
                        running_pred_label,
                        running_pred_conf,
                        phase,
                        epoch,
                        tboard_writer,
                    )

                    epoch_msg = f"{phase: <8} -- {epoch}/{end_epoch} -- "
                    epoch_msg = self.gen_epoch_msg(phase, epoch_msg)

                    if phase.lower() in valid_phase_names:
                        self.cprint("[INFO]", self.color_dred, epoch_msg + "\n")
                    else:
                        self.cprint("[INFO]", self.color_dgreen, epoch_msg)

                # labels/confidence
                self.pred_conf.extend(running_pred_conf)
                self.pred_label.extend(running_pred_label)
                self.orig_label.extend(running_orig_label)

                # Update best_loss and _epoch?
                if phase.lower() in valid_phase_names and epoch_loss < self.best_loss:
                    self.best_loss = epoch_loss
                    self.best_epoch = epoch
                    best_model_wts = copy.deepcopy(self.model.state_dict())

                if phase.lower() in valid_phase_names:
                    if epoch % tmp_file_save_freq == 0:
                        print(
                            f"SAVE temp file: {self.tmp_save_filename} | set .last_epoch: {epoch}"  # noqa
                        )
                        tmp_str = f"[INFO] SAVE temp file: {self.tmp_save_filename} | set .last_epoch: {epoch}\n"  # noqa
                        print(self.color_lgrey + tmp_str + self.color_reset)
                        self.last_epoch = epoch
                        self.save(self.tmp_save_filename, force=True)

        time_elapsed = time.time() - since
        print(f"Total time: {time_elapsed // 60:.0f}m {time_elapsed % 60:.0f}s")

        # load best model weights
        self.model.load_state_dict(best_model_wts)

        # --- SAVE model/object
        if phase.lower() in train_phase_names + valid_phase_names:
            self.last_epoch = epoch
            if save_model_dir is not None:
                save_filename = f"checkpoint_{self.best_epoch}.pkl"
                save_model_path = os.path.join(save_model_dir, save_filename)
                self.save(save_model_path, force=True)
                info_path = os.path.join(save_model_dir, "info.txt")
                with open(info_path, "a+") as f:
                    f.writelines(f"{save_filename},{self.best_loss:.5f}\n")

                print(
                    f"[INFO] Save model epoch: {self.best_epoch} with least valid loss: {self.best_loss:.4f}"  # noqa
                )
                print(f"[INFO] Path: {save_model_path}")

    def show_sample(
        self,
        set_name: Optional[str] = "train",
        batch_number: Optional[int] = 1,
        print_batch_info: Optional[bool] = True,
        figsize: Optional[Tuple[int, int]] = (15, 10),
    ) -> None:
        """
        Displays a sample of training or validation data in a grid format with
        their corresponding class labels.

        Parameters
        ----------
        set_name : str, optional
            Name of the dataset (``train``/``validation``) to display the
            sample from, by default ``"train"``.
        batch_number : int, optional
            Number of batches to display, by default ``1``.
        print_batch_info : bool, optional
            Whether to print information about the batch size, by default
            ``True``.
        figsize : tuple, optional
            Figure size (width, height) in inches, by default ``(15, 10)``.

        Returns
        -------
        None
            Displays the sample images with their corresponding class labels.

        Raises
        ------
        StopIteration
            If the specified number of batches to display exceeds the total
            number of batches in the dataset.

        Notes
        -----
        This method uses the dataloader of the ``ImageClassifierData`` class
        and the ``torchvision.utils.make_grid`` function to display the sample
        data in a grid format. It also calls the ``_imshow`` method of the
        ``ImageClassifierData`` class to show the sample data.
        """
        if print_batch_info:
            # print info about batch size
            self.batch_info()

        dl_iter = iter(self.dataloader[set_name])
        for _ in range(batch_number):
            # Get a batch of training data
            inputs1, inputs2, classes = next(dl_iter)

        # Make a grid from batch
        out = torchvision.utils.make_grid(inputs1)
        self._imshow(
            out,
            title=str([self.class_names[int(x)] for x in classes]),
            figsize=figsize,
        )

        out = torchvision.utils.make_grid(inputs2)
        self._imshow(
            out,
            title=str([self.class_names[int(x)] for x in classes]),
            figsize=figsize,
        )

    def layerwise_lr(
        self,
        min_lr: float,
        max_lr: float,
        ltype: Optional[str] = "linspace",
        sep_group_names: List[str] = ["features1", "features2"],
    ) -> List[Dict]:
        """
        Calculates layer-wise learning rates for a given set of model
        parameters.

        Parameters
        ----------
        min_lr : float
            The minimum learning rate to be used.
        max_lr : float
            The maximum learning rate to be used.
        ltype : str, optional
            The type of sequence to use for spacing the specified interval
            learning rates. Can be either ``"linspace"`` or ``"geomspace"``,
            where `"linspace"` uses evenly spaced learning rates over a
            specified interval and `"geomspace"` uses learning rates spaced
            evenly on a log scale (a geometric progression). Defaults to
            ``"linspace"``.
        sep_group_names : list, optional
            A list of strings containing the names of parameter groups. Layers
            belonging to each group will be assigned the same learning rate.
            Defaults to ``["features1", "features2"]``.

        Returns
        -------
        list of dicts
            A list of dictionaries containing the parameters and learning
            rates for each layer.
        """
        list2optim = []
        for group in range(len(sep_group_names)):
            # count number of layers in this group
            num_grp_layers = 0
            for i, (name, params) in enumerate(self.model.named_parameters()):
                if sep_group_names[group] in name:
                    num_grp_layers += 1

            # define layer-wise learning rates
            if ltype.lower() in ["line", "linear", "linspace"]:
                list_lrs = np.linspace(min_lr, max_lr, num_grp_layers)
            elif ltype.lower() in ["log", "geomspace"]:
                list_lrs = np.geomspace(min_lr, max_lr, num_grp_layers)
            else:
                raise NotImplementedError(
                    "Implemented methods are: linspace and geomspace"
                )

            # assign learning rates
            i_count = 0
            for _, (name, params) in enumerate(self.model.named_parameters()):
                if not sep_group_names[group] in name:
                    continue
                list2optim.append({"params": params, "lr": list_lrs[i_count]})
                i_count += 1

        return list2optim

    def inference_sample_results(
        self,
        num_samples: Optional[int] = 6,
        class_index: Optional[int] = 0,
        set_name: Optional[str] = "train",
        min_conf: Optional[Union[None, float]] = None,
        max_conf: Optional[Union[None, float]] = None,
        figsize: Optional[Tuple[int, int]] = (15, 15),
    ) -> None:
        """
        Performs inference on a given dataset and displays results for a
        specified class.

        Parameters
        ----------
        num_samples : int, optional
            The number of sample results to display. Defaults to ``6``.
        class_index : int, optional
            The index of the class for which to display results. Defaults to
            ``0``.
        set_name : str, optional
            The name of the dataset split to use for inference. Defaults to
            ``"train"``.
        min_conf : float, optional
            The minimum confidence score for a sample result to be displayed.
            Samples with lower confidence scores will be skipped. Defaults to
            ``None``.
        max_conf : float, optional
            The maximum confidence score for a sample result to be displayed.
            Samples with higher confidence scores will be skipped. Defaults to
            ``None``.
        figsize : tuple[int, int], optional
            Figure size (width, height) in inches, displaying the sample
            results. Defaults to ``(15, 15)``.

        Returns
        -------
        None
        """

        # eval mode, keep track of the current mode
        was_training = self.model.training
        self.model.eval()

        fig = plt.figure(figsize=figsize)

        counter = 0
        with torch.no_grad():
            for inputs1, inputs2, labels in iter(self.dataloader[set_name]):
                inputs1 = inputs1.to(self.device)
                labels = labels.to(self.device)
                inputs2 = inputs2.to(self.device)

                outputs = self.model(inputs1, inputs2)
                pred_conf = torch.nn.functional.softmax(outputs, dim=1) * 100.0
                _, preds = torch.max(outputs, 1)

                # go through images in batch
                for j in range(len(preds)):
                    pred_ind = int(preds[j])
                    if pred_ind != class_index:
                        continue
                    if (min_conf is not None) and (pred_conf[j][pred_ind] < min_conf):
                        continue
                    if (max_conf is not None) and (pred_conf[j][pred_ind] > max_conf):
                        continue

                    counter += 1

                    class_name = self.class_names[pred_ind]
                    conf_score = pred_conf[j][pred_ind]
                    ax = plt.subplot(int(num_samples / 2.0), 3, counter)
                    ax.axis("off")
                    ax.set_title(f"{class_name} | {conf_score:.3f}")

                    inp = inputs1.cpu().data[j].numpy().transpose((1, 2, 0))
                    inp = np.clip(inp, 0, 1)
                    plt.imshow(inp)

                    if counter == num_samples:
                        self.model.train(mode=was_training)
                        plt.show()
                        return

            self.model.train(mode=was_training)
            plt.show()
