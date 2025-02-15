import cv2
import numpy as np
import time 
from rknnlite.api import RKNNLite
class SCRFD():
    def __init__(self):
        self.inpWidth = 640
        self.inpHeight = 640
        self.confThreshold = 0.5
        self.nmsThreshold = 0.5
        self.net = RKNNLite()
        self.net.load_rknn('./best.rknn')
        self.net.init_runtime()
        self.keep_ratio = True
        self.fmc = 3
        self._feat_stride_fpn = [8, 16, 32]
        self._num_anchors = 2
    def resize_image(self, srcimg):
        padh, padw, newh, neww = 0, 0, self.inpHeight, self.inpWidth
        if self.keep_ratio and srcimg.shape[0] != srcimg.shape[1]:
            hw_scale = srcimg.shape[0] / srcimg.shape[1]
            if hw_scale > 1:
                newh, neww = self.inpHeight, int(self.inpWidth / hw_scale)
                img = cv2.resize(srcimg, (neww, newh), interpolation=cv2.INTER_AREA)
                padw = int((self.inpWidth - neww) * 0.5)
                img = cv2.copyMakeBorder(img, 0, 0, padw, self.inpWidth - neww - padw, cv2.BORDER_CONSTANT,
                                         value=0)  # add border
            else:
                newh, neww = int(self.inpHeight * hw_scale) + 1, self.inpWidth
                img = cv2.resize(srcimg, (neww, newh), interpolation=cv2.INTER_AREA)
                padh = int((self.inpHeight - newh) * 0.5)
                img = cv2.copyMakeBorder(img, padh, self.inpHeight - newh - padh, 0, 0, cv2.BORDER_CONSTANT, value=0)
        else:
            img = cv2.resize(srcimg, (self.inpWidth, self.inpHeight), interpolation=cv2.INTER_AREA)
        return img, newh, neww, padh, padw
    def distance2bbox(self, points, distance, max_shape=None):
        x1 = points[:, 0] - distance[:, 0]
        y1 = points[:, 1] - distance[:, 1]
        x2 = points[:, 0] + distance[:, 2]
        y2 = points[:, 1] + distance[:, 3]
        if max_shape is not None:
            x1 = x1.clamp(min=0, max=max_shape[1])
            y1 = y1.clamp(min=0, max=max_shape[0])
            x2 = x2.clamp(min=0, max=max_shape[1])
            y2 = y2.clamp(min=0, max=max_shape[0])
        return np.stack([x1, y1, x2, y2], axis=-1)
    def distance2kps(self, points, distance, max_shape=None):
        preds = []
        for i in range(0, distance.shape[1], 2):
            px = points[:, i % 2] + distance[:, i]
            py = points[:, i % 2 + 1] + distance[:, i + 1]
            if max_shape is not None:
                px = px.clamp(min=0, max=max_shape[1])
                py = py.clamp(min=0, max=max_shape[0])
            preds.append(px)
            preds.append(py)
        return np.stack(preds, axis=-1)
    def detect(self, srcimg):
        img, newh, neww, padh, padw = self.resize_image(srcimg)
        img = np.expand_dims(img,axis=0)
        # print('shape:',img.shape)
        start =time.time()
        outs = self.net.inference(inputs=[img])[0]
        end = time.time()
        print('inference time:',end-start,'FPS:',round(1/(end-start),2))
        # for i in range(0,9):
        #     outs[i]=np.squeeze(outs[i],axis=-1)
        # outs = outs[::3] + outs[1::3] + outs[2::3]
        # scores_list, bboxes_list, kpss_list = [], [], []
        # for idx, stride in enumerate(self._feat_stride_fpn):
        #     scores = outs[idx * self.fmc][0]
        #     bbox_preds = outs[idx * self.fmc + 1][0] * stride
        #     kps_preds = outs[idx * self.fmc + 2][0] * stride
        #     height = 640 // stride
        #     width = 640 // stride
        #     anchor_centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
        #     anchor_centers = (anchor_centers * stride).reshape((-1, 2))
        #     if self._num_anchors > 1:
        #         anchor_centers = np.stack([anchor_centers] * self._num_anchors, axis=1).reshape((-1, 2))
        #     pos_inds = np.where(scores >= self.confThreshold)[0]
        #     bboxes = self.distance2bbox(anchor_centers, bbox_preds)
        #     pos_scores = scores[pos_inds]
        #     pos_bboxes = bboxes[pos_inds]
        #     scores_list.append(pos_scores)
        #     bboxes_list.append(pos_bboxes)
        #     kpss = self.distance2kps(anchor_centers, kps_preds)
        #     kpss = kpss.reshape((kpss.shape[0], -1, 2))
        #     pos_kpss = kpss[pos_inds]
        #     kpss_list.append(pos_kpss)
        # scores = np.vstack(scores_list).ravel()
        # bboxes = np.vstack(bboxes_list)
        # kpss = np.vstack(kpss_list)
        bboxes = outs[0][:,:4]
        scores = outs[0][:,4]
        # bboxes[:, 2:4] = bboxes[:, 2:4] - bboxes[:, 0:2]
        ratioh, ratiow = srcimg.shape[0] / newh, srcimg.shape[1] / neww
        bboxes[:, 0] = (bboxes[:, 0] - padw) * ratiow
        bboxes[:, 1] = (bboxes[:, 1] - padh) * ratioh
        bboxes[:, 2] = bboxes[:, 2] * ratiow
        bboxes[:, 3] = bboxes[:, 3] * ratioh
        # kpss[:, :, 0] = (kpss[:, :, 0] - padw) * ratiow
        # kpss[:, :, 1] = (kpss[:, :, 1] - padh) * ratioh
        scores_index = scores>self.nmsThreshold
        bboxes = bboxes[scores_index]
        scores = scores[scores_index]

        indices = cv2.dnn.NMSBoxes(bboxes.tolist(), scores.tolist(), self.confThreshold, self.nmsThreshold)
        for i in indices:
            xmin, ymin, xamx, ymax = int(bboxes[i, 0]- bboxes[i, 2]/2), int(bboxes[i, 1]-bboxes[i, 3]/2), int(bboxes[i, 0] + bboxes[i, 2]/2), int(bboxes[i, 1] + bboxes[i, 3]/2)
            cv2.rectangle(srcimg, (xmin, ymin), (xamx, ymax), (0, 0, 255), thickness=3)
            cv2.putText(srcimg, str(round(scores[i], 3)), (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), thickness=3)
        return srcimg

if __name__ == '__main__':
    mynet = SCRFD()
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
    win = 'atk scrfd face detection'
    cv2.namedWindow(win, 0)
    cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    while 1:
        ret,srcimg = cap.read()
        srcimg = cv2.rotate(srcimg,cv2.ROTATE_90_COUNTERCLOCKWISE)

        outimg = mynet.detect(srcimg)

        cv2.imshow(win, outimg)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            cap.release()
    cv2.destroyAllWindows()