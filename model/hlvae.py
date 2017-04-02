import torch.nn as nn

from model.sequence_to_image import SequenceToImage


class HLVAE(nn.Module):
    def __init__(self, params):
        super(HLVAE, self).__init__()

        self.params = params

        self.seq_to_image = SequenceToImage(params)

    def forward(self, drop_prob=0,
                encoder_word_input=None, encoder_character_input=None,
                target_images=None, target_image_sizes=None,
                real_images=None,
                decoder_word_input=None,
                z=None):
        pass

