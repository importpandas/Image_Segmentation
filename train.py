import fire
import os
from tqdm import tqdm
from torch import optim
import torchvision
from torch.utils.data import DataLoader
import torch.nn.functional as F
from utils import parse_config_or_kwargs, store_yaml

from utils import check_dir, get_logger_2
from utils import set_seed
from new_dataset import ImageFolder
from network import U_Net, R2U_Net, AttU_Net, R2AttU_Net
from evaluation import *


def save_checkpoint(state_dict, save_path):
    torch.save(state_dict, save_path)


def test(model, test_loader, conf, logger, epoch):
    model.eval()
    acc = 0.  # Accuracy
    SE = 0.  # Sensitivity (Recall)
    SP = 0.  # Specificity
    PC = 0.  # Precision
    F1 = 0.  # F1 Score
    JS = 0.  # Jaccard Similarity
    DC = 0.  # Dice Coefficient
    length = 0

    result_store_dir = os.path.join(conf['exp_dir'], 'result')
    check_dir(result_store_dir)
    store_path = os.path.join(result_store_dir, 'epoch-{}-{}.png')

    with torch.no_grad():
        for iter_idx, (images, labels) in enumerate(test_loader):
            images = images.to(conf['device'])
            labels = labels.to(conf['device'])
            seg_res = model(images)
            seg_prob = F.sigmoid(seg_res)

            acc += get_accuracy(seg_prob, labels)
            SE += get_sensitivity(seg_prob, labels)
            SP += get_specificity(seg_prob, labels)
            PC += get_precision(seg_prob, labels)
            F1 += get_F1(seg_prob, labels)
            JS += get_JS(seg_prob, labels)
            DC += get_DC(seg_prob, labels)
            length += images.size(0)

            torchvision.utils.save_image(images.data.cpu(), store_path.format(epoch, 'image'))
            torchvision.utils.save_image(labels.data.cpu(), store_path.format(epoch, 'GT'))
            torchvision.utils.save_image(seg_prob.data.cpu(), store_path.format(epoch, 'SR'))
            torchvision.utils.save_image((seg_prob > 0.5).float().data.cpu(), store_path.format(epoch, 'PRE'))


    acc = acc / length
    SE = SE / length
    SP = SP / length
    PC = PC / length
    F1 = F1 / length
    JS = JS / length
    DC = DC / length
    unet_score = JS + DC

    logger.info("[Test] Epoch: [{}/{}] Acc: {:.3f} SE: {:.3f}  SP: {:.3f} PC: {:.3f} F1: {:.3f} JS: {:.3f} "
                "DC: {:.3f} Unet_score: {:.3f}".format(epoch, conf['num_epochs'],
                                                 acc, SE, SP, PC, F1, JS, DC,
                                                 unet_score))

    return acc, unet_score


def train(model, train_loader, test_loader, optimizer, conf, logger):
    model.train()
    best_unet_score = 0.

    for epoch in range(conf['num_epochs']):
        acc = 0.  # Accuracy
        SE = 0.  # Sensitivity (Recall)
        SP = 0.  # Specificity
        PC = 0.  # Precision
        F1 = 0.  # F1 Score
        JS = 0.  # Jaccard Similarity
        DC = 0.  # Dice Coefficient
        length = 0
        epoch_loss = 0.0

        model.train()
        for iter_idx, (images, labels) in enumerate(tqdm(train_loader)):

            images = images.to(conf['device'])
            labels = labels.to(conf['device'])

            optimizer.zero_grad()
            seg_res = model(images)
            seg_prob = F.sigmoid(seg_res)

            seg_res_flat = seg_res.view(seg_res.size(0), -1)
            labels_flat = labels.view(labels.size(0), -1)

            loss = F.binary_cross_entropy_with_logits(seg_res_flat, labels_flat)
            epoch_loss += loss.item()
            loss.backward()
            optimizer.step()

            acc += get_accuracy(seg_prob, labels)
            SE += get_sensitivity(seg_prob, labels)
            SP += get_specificity(seg_prob, labels)
            PC += get_precision(seg_prob, labels)
            F1 += get_F1(seg_prob, labels)
            JS += get_JS(seg_prob, labels)
            DC += get_DC(seg_prob, labels)
            length += images.size(0)

        acc = acc / length
        SE = SE / length
        SP = SP / length
        PC = PC / length
        F1 = F1 / length
        JS = JS / length
        DC = DC / length
        epoch_loss /= len(train_loader)

        logger.info("[Train] Epoch: [{}/{}] Acc: {:.3f} SE: {:.3f}  SP: {:.3f} PC: {:.3f} F1: {:.3f} JS: {:.3f} "
                    "DC: {:.3f} Loss: {:.3f}".format(epoch, conf['num_epochs'],
                                                     acc, SE, SP, PC, F1, JS, DC,
                                                     epoch_loss))

        test_acc, unet_score = test(model, test_loader, conf, logger, epoch)


def main(config, gpu_id, kwargs):
    conf = parse_config_or_kwargs(config, **kwargs)

    check_dir(conf['exp_dir'])
    logger = get_logger_2(os.path.join(conf['exp_dir'], 'train.log'), "[ %(asctime)s ] %(message)s")

    store_path = os.path.join(conf['exp_dir'], 'config.yaml')
    store_yaml(config, store_path, **kwargs)

    cuda_id = 'cuda:' + str(gpu_id)
    conf['device'] = torch.device(cuda_id if torch.cuda.is_available() else 'cpu')

    model_dir = os.path.join(conf['exp_dir'], 'models')
    check_dir(model_dir)
    conf['checkpoint_format'] = os.path.join(model_dir, '{}.th')

    set_seed(conf['seed'])

    # -------------------------- get loss_calculator and model --------------------------

    model = eval(conf['model_type'])()
    model = model.to(conf['device'])
    optimizer = optim.Adam(model.parameters(), lr=conf['lr'], betas=(0.5, 0.999))

    logger.info("Model type: {}".format(conf['model_type']))
    logger.info(optimizer)

    train_set = ImageFolder(root=conf['root'], mode='train', augmentation_prob=conf['aug_prob'],
                            crop_size_min=conf['crop_size_min'], crop_size_max=conf['crop_size_max'],
                            data_num=conf['data_num'])
    train_loader = DataLoader(dataset=train_set, batch_size=conf['batch_size'],
                              shuffle=conf['shuffle'], num_workers=conf['num_workers'])

    test_set = ImageFolder(root=conf['root'], mode='test')
    test_loader = DataLoader(dataset=test_set, batch_size=5,
                             shuffle=False, num_workers=1)

    train(model, train_loader, test_loader, optimizer, conf, logger)


if __name__ == '__main__':
    fire.Fire(main)