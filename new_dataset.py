import os
import random
import numpy as np
from torch.utils import data
from torchvision import transforms as T
from torchvision.transforms import functional as F
from PIL import Image
import glob


class ImageFolder(data.Dataset):
    def __init__(self, root, mode='train', augmentation_prob=0.4, crop_size_min=300,
                 crop_size_max=500, data_num=0):
        """Initializes image paths and preprocessing module."""
        self.root = root
        self.crop_size_min = crop_size_min
        self.crop_size_max = crop_size_max
        self.data_num = data_num

        data_dir_name = mode + '_img'
        label_dir_name = mode + '_label'

        self.data_list = []
        data_paths = glob.glob(os.path.join(root, 'new_{}_set'.format(mode), data_dir_name, '*.png'))
        for data_path in data_paths:
            label_path = data_path.replace(data_dir_name, label_dir_name)
            self.data_list.append((Image.open(data_path), Image.open(label_path)))

        self.mode = mode
        self.RotationDegree = [0, 90, 180, 270]
        self.augmentation_prob = augmentation_prob

    def __getitem__(self, index):
        """Reads an image from a file and preprocesses it and returns."""
        image, GT = self.data_list[index % len(self.data_list)]

        Transform = []
        p_transform = random.random()

        if (self.mode == 'train') and p_transform <= self.augmentation_prob:
            RotationDegree = random.randint(0, 3)
            RotationDegree = self.RotationDegree[RotationDegree]

            Transform.append(T.RandomRotation((RotationDegree, RotationDegree)))

            RotationRange = random.randint(-10, 10)
            Transform.append(T.RandomRotation((RotationRange, RotationRange)))

            Transform = T.Compose(Transform)
            image = Transform(image)
            GT = Transform(GT)

            crop_len = random.randint(self.crop_size_min, self.crop_size_max)
            i, j, h, w = T.RandomCrop.get_params(image, output_size=(crop_len, crop_len))
            image = F.crop(image, i, j, h, w)
            GT = F.crop(GT, i, j, h, w)

            if random.random() < 0.5:
                image = F.hflip(image)
                GT = F.hflip(GT)

            if random.random() < 0.5:
                image = F.vflip(image)
                GT = F.vflip(GT)

            Transform = []

        Transform.append(T.Resize((512, 512)))
        Transform.append(T.ToTensor())
        Transform = T.Compose(Transform)

        image = Transform(image)
        GT = Transform(GT).int()

        Norm_ = T.Normalize((0.5,), (0.5,))
        image = Norm_(image)

        return image, GT

    def __len__(self):
        """Returns the total number of font files."""
        if self.data_num > 0:
            return self.data_num
        else:
            return len(self.data_list)


def get_loader(image_path, image_size, batch_size, num_workers=2, mode='train', augmentation_prob=0.4):
    """Builds and returns Dataloader."""

    dataset = ImageFolder(root=image_path, mode=mode, augmentation_prob=augmentation_prob)
    data_loader = data.DataLoader(dataset=dataset,
                                  batch_size=batch_size,
                                  shuffle=True,
                                  num_workers=num_workers)
    return data_loader


if __name__ == '__main__':
    root = '/Users/chenzhengyang/gitRepo/Image_Segmentation/data'
    dataset = ImageFolder(root, mode='test', augmentation_prob=0.4)

    data_loader = data.DataLoader(dataset=dataset,
                                  batch_size=5,
                                  shuffle=False,
                                  num_workers=1)

    import torchvision
    for data, label in data_loader:
        print(label.shape)
        torchvision.utils.save_image(label.float()*0.7, 'tmp/tmp.png')
        break