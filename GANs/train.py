import torch
from torch.utils.data import DataLoader
import pytorch_lightning as pl
from torchvision import utils, transforms
import numpy as np

from .DCGAN import Generator, Discriminator
from .encoder import Encoder
from .loss import GanLoss
from .utils import GanDataset


class GAN(pl.LightningModule):
    def __init__(
            self,
            data_path: str,
            loss_type: str = 'non_saturating',
            img_size: int = 64,
            batch_size: int = 16,
            lr_gen = 1e-04,
            lr_dis = 1e-04
    ):
        super(GAN, self).__init__()

        self.noise_channels = 128
        self.latent_dim_channels = 128

        self.lr_gen = lr_gen
        self.lr_dis = lr_dis

        self.loss = GanLoss(loss_type)

        self.dataset = np.load(data_path)
        self.train_dataset = GanDataset(self.dataset, transforms.ToTensor())
        self.batch_size = batch_size

        self.encoder = Encoder(img_size, self.latent_dim_channels)

        self.gen = Generator(self.noise_channels+self.latent_dim_channels, loss_type)
        self.dis = Discriminator()

    def forward(self, noise):
        return self.gen(noise)

    def training_step(self, batch, batch_idx, optimizer_idx):
        imgs, slices = batch

        noise = torch.randn(len(slices), self.noise_channels).to(imgs.device)
        latent_slice_features = self.encoder(slices)
        noise = torch.cat([noise, latent_slice_features], dim=1)

        real_preds = self.dis(imgs)

        fake_images = self.gen(noise)
        fake_preds = self.dis(fake_images)

        if optimizer_idx == 0:
            loss = self.loss(fake_preds, None, fake_images[:, :, 0, :, :], imgs[:, :, 0, :, :])
        elif optimizer_idx == 1:
            loss = self.loss(fake_preds, real_preds, None, None)

        assert loss.shape == ()

        loss_name = 'loss_gen' if optimizer_idx == 0 else 'loss_dis'
        self.log(loss_name, loss, prog_bar=True)

        return loss

    @torch.no_grad()
    def validation_step(self, batch, batch_idx):
        imgs, slices = batch

        noise = torch.randn(len(slices), self.noise_channels).to(imgs.device)
        latent_slice_features = self.encoder(slices)
        noise = torch.cat([noise, latent_slice_features], dim=1)

        fake_images = self.gen(noise).detach().cpu()
        grid = utils.make_grid(fake_images[:, :, 0, :, :], nrow=4)
        self.logger.experiment.add_image('generated_images', grid, self.current_epoch)

    def configure_optimizers(self):
        opt_gen = torch.optim.Adam(self.gen.parameters(), lr=self.lr_gen, betas=(0.0, 0.999))
        opt_dis = torch.optim.Adam(self.dis.parameters(), lr=self.lr_dis, betas=(0.0, 0.9999))
        return [opt_gen, opt_dis], []

    def train_dataloader(self):
        return DataLoader(self.train_dataset, num_workers=8, batch_size=self.batch_size, shuffle=True)

    def val_dataloader(self):
        return DataLoader(self.train_dataset, num_workers=8, batch_size=self.batch_size, shuffle=False)




