import argparse
import os
import numpy as np
import torch as t
import torch.nn.functional as F
from torch.optim import Adam
from utils.batchloader import BatchLoader
from utils.parameters import Parameters
from model.cdvae import CDVAE

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='CDVAE')
    parser.add_argument('--num-iterations', type=int, default=450000, metavar='NI',
                        help='num iterations (default: 450000)')
    parser.add_argument('--batch-size', type=int, default=30, metavar='BS',
                        help='batch size (default: 30)')
    parser.add_argument('--use-cuda', type=bool, default=False, metavar='CUDA',
                        help='use cuda (default: False)')
    parser.add_argument('--learning-rate', type=float, default=0.0005, metavar='LR',
                        help='learning rate (default: 0.0005)')
    parser.add_argument('--dropout', type=float, default=0.12, metavar='TDR',
                        help='dropout (default: 0.12)')
    parser.add_argument('--save', type=str, default=None, metavar='TS',
                        help='path where save trained model to (default: None)')
    args = parser.parse_args()

    batch_loader = BatchLoader(force_preprocessing=True)
    parameters = Parameters(batch_loader.vocab_size)

    cdvae = CDVAE(parameters)
    if args.use_cuda:
        cdvae = cdvae.cuda()

    optimizer_ru = Adam(cdvae.vae_ru.learnable_parameters(), args.learning_rate, eps=1e-4)
    optimizer_en = Adam(cdvae.vae_en.learnable_parameters(), args.learning_rate, eps=1e-4)

    for iteration in range(args.num_iterations):

        (input, dec_input_ru, dec_target_ru), (input_en, dec_input_en, dec_target_en) = \
            batch_loader.next_batch(args.batch_size, 'train', args.use_cuda)

        '''losses from cdvae is tuples of ru and en losses respectively'''
        loss_ru, loss_en = cdvae(args.dropout,
                                 input, input_en,
                                 dec_input_ru, dec_input_en,
                                 dec_target_ru, dec_target_en,
                                 iteration)

        optimizer_ru.zero_grad()
        loss_ru[0].backward(retain_variables=True)
        optimizer_ru.step()

        optimizer_en.zero_grad()
        loss_en[0].backward()
        optimizer_en.step()

        if iteration % 10 == 0:
            print('\n')
            print('|--------------------------------------|')
            print(iteration)
            print('|---reconst-loss--kl-loss--cd-loss-----|')
            print('|---------------ru---------------------|')
            print(loss_ru[1].data.cpu().numpy()[0],
                  loss_ru[2].data.cpu().numpy()[0],
                  loss_ru[3].data.cpu().numpy()[0])
            print('|---------------en---------------------|')
            print(loss_en[1].data.cpu().numpy()[0],
                  loss_en[2].data.cpu().numpy()[0],
                  loss_en[3].data.cpu().numpy()[0])
            print('|--------------------------------------|')

        if iteration % 20 == 0:
            (input, _, _), _ = batch_loader.next_batch(1, 'valid', args.use_cuda)

            print('vae ru-en')
            print(''.join([batch_loader.idx_to_char['ru'][idx] for idx in input.data.cpu().numpy()[0]]))
            print(cdvae.translate(input, ['ru', 'en'], batch_loader))
            print('-----------')
            print('vae ru-ru')
            (input, _, _), _ = batch_loader.next_batch(1, 'valid', args.use_cuda)
            print(''.join([batch_loader.idx_to_char['ru'][idx] for idx in input.data.cpu().numpy()[0]]))

            print(cdvae.translate(input, ['ru', 'ru'], batch_loader))
            print('-----------')