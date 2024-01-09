# Copyright (c) OpenMMLab. All rights reserved.
import numpy as np
import os
import mmcv
import torch
import torch.distributed as dist


def single_gpu_test(model,data_loader):
    model.eval()
    results = []
    dataset = data_loader.dataset
    prog_bar = mmcv.ProgressBar(len(dataset))
    for i,data in enumerate(data_loader):
        with torch.no_grad():
            result = model(return_loss=False, rescale=True, **data)
        # np.save(f'/mnt/allfile/project/RenderOcc/result/{i}',result)
        results.extend(result)

        batch_size = len(result)
        for _ in range(batch_size):
            prog_bar.update()
    return results

