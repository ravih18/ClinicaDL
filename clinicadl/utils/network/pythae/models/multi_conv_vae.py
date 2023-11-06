import torch

from clinicadl.utils.network.pythae.pythae_utils import Encoder_VAE, Decoder

from clinicadl.utils.network.vae.vae_layers import (
    # EncoderLayer3D,
    DecoderLayer3D,
    Flatten,
    Unflatten3D,
    MultiConvEncoderBlock3D,
    MultiConvDecoderBlock3D,
)

from clinicadl.utils.network.pythae.pythae_utils import BasePythae


class multi_conv_VAE(BasePythae):
    def __init__(
        self,
        input_size,
        first_layer_channels,
        n_conv_encoder,
        feature_size,
        latent_space_size,
        n_conv_decoder,
        last_layer_channels,
        last_layer_conv,
        gpu,
        n_conv_per_block,
    ):
        from pythae.models import VAE, VAEConfig

        _, _ = super(multi_conv_VAE, self).__init__(
            input_size=input_size,
            first_layer_channels=first_layer_channels,
            n_conv_encoder=n_conv_encoder,
            feature_size=feature_size,
            latent_space_size=latent_space_size,
            n_conv_decoder=n_conv_decoder,
            last_layer_channels=last_layer_channels,
            last_layer_conv=last_layer_conv,
            gpu=gpu,
        )

        encoder_layers, mu_layer, logvar_layer, decoder_layers = build_encoder_decoder(
            input_size=input_size,
            first_layer_channels=first_layer_channels,
            n_conv_encoder=n_conv_encoder,
            feature_size=feature_size,
            latent_space_size=latent_space_size,
            n_conv_decoder=n_conv_decoder,
            last_layer_channels=last_layer_channels,
            last_layer_conv=last_layer_conv,
            n_conv_per_block=n_conv_per_block,
        )

        encoder = Encoder_VAE(encoder_layers, mu_layer, logvar_layer)
        decoder = Decoder(decoder_layers)

        model_config = VAEConfig(
            input_dim=self.input_size,
            latent_dim=self.latent_space_size,
            uses_default_encoder=False,
            uses_default_decoder=False,
        )

        self.model = VAE(
            model_config=model_config,
            encoder=encoder,
            decoder=decoder,
        )

    def get_trainer_config(self, output_dir, num_epochs, learning_rate, batch_size):
        from pythae.trainers import BaseTrainerConfig

        return BaseTrainerConfig(
            output_dir=output_dir,
            num_epochs=num_epochs,
            learning_rate=learning_rate,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            # amp=True,
        )


def build_encoder_decoder(
    input_size=(1, 80, 96, 80),
    # input_size=(1, 169, 208, 179),
    first_layer_channels=32,
    n_conv_encoder=3,
    feature_size=0,
    latent_space_size=128,
    n_conv_decoder=3,
    last_layer_channels=32,
    last_layer_conv=False,
    n_conv_per_block=3,
):
    input_c = input_size[0]
    input_d = input_size[1]
    input_h = input_size[2]
    input_w = input_size[3]

    # ENCODER
    encoder_layers = []
    # Input Layer
    encoder_layers.append(
        MultiConvEncoderBlock3D(
            input_c, first_layer_channels, n_conv_per_block=n_conv_per_block
        )
    )  # EncoderLayer3D

    # Conv Layers
    for i in range(n_conv_encoder - 1):
        encoder_layers.append(
            MultiConvEncoderBlock3D(
                first_layer_channels * 2**i,
                first_layer_channels * 2 ** (i + 1),
                n_conv_per_block=n_conv_per_block,
            )
        )
        # Construct output paddings
    # Compute size of the feature space
    n_pix_encoder = (
        first_layer_channels
        * 2 ** (n_conv_encoder - 1)
        * (input_d // (2**n_conv_encoder))
        * (input_h // (2**n_conv_encoder))
        * (input_w // (2**n_conv_encoder))
    )
    # Flatten
    encoder_layers.append(Flatten())
    # Intermediate feature space
    if feature_size == 0:
        feature_space = n_pix_encoder
    else:
        feature_space = feature_size
        encoder_layers.append(
            torch.nn.Sequential(
                torch.nn.Linear(n_pix_encoder, feature_space), torch.nn.ReLU()
            )
        )
    encoder = torch.nn.Sequential(*encoder_layers)

    # LATENT SPACE
    mu_layer = torch.nn.Linear(feature_space, latent_space_size)
    var_layer = torch.nn.Linear(feature_space, latent_space_size)

    # DECODER

    # automatically compute padding
    d, h, w = input_d, input_h, input_w
    decoder_output_padding = []
    decoder_output_padding.append([d % 2, h % 2, w % 2])
    d, h, w = d // 2, h // 2, w // 2
    for i in range(n_conv_decoder - 1):
        decoder_output_padding.append([d % 2, h % 2, w % 2])
        d, h, w = d // 2, h // 2, w // 2

    n_pix_decoder = (
        last_layer_channels
        * 2 ** (n_conv_decoder - 1)
        * (input_d // (2**n_conv_decoder))
        * (input_h // (2**n_conv_decoder))
        * (input_w // (2**n_conv_decoder))
    )

    decoder_layers = []
    # Intermediate feature space
    if feature_size == 0:
        decoder_layers.append(
            torch.nn.Sequential(
                torch.nn.Linear(latent_space_size, n_pix_decoder),
                torch.nn.ReLU(),
            )
        )
    else:
        decoder_layers.append(
            torch.nn.Sequential(
                torch.nn.Linear(latent_space_size, feature_size),
                torch.nn.ReLU(),
                torch.nn.Linear(feature_size, n_pix_decoder),
                torch.nn.ReLU(),
            )
        )
    # Unflatten
    decoder_layers.append(
        Unflatten3D(
            last_layer_channels * 2 ** (n_conv_decoder - 1),
            input_d // (2**n_conv_decoder),
            input_h // (2**n_conv_decoder),
            input_w // (2**n_conv_decoder),
        )
    )
    # Decoder layers
    for i in range(n_conv_decoder - 1, 0, -1):
        decoder_layers.append(
            MultiConvDecoderBlock3D(
                last_layer_channels * 2 ** (i),
                last_layer_channels * 2 ** (i - 1),
                output_padding=decoder_output_padding[i],
                n_conv_per_block=n_conv_per_block,
            )
        )
    # Output conv layer
    if last_layer_conv:
        last_layer = torch.nn.Sequential(
            DecoderLayer3D(
                last_layer_channels,
                last_layer_channels,
                4,
                stride=2,
                padding=1,
                output_padding=decoder_output_padding[0],
            ),
            torch.nn.Conv3d(last_layer_channels, input_c, 3, stride=1, padding=1),
            torch.nn.Sigmoid(),
        )

    else:
        last_layer = torch.nn.Sequential(
            torch.nn.ConvTranspose3d(
                last_layer_channels,
                input_c,
                4,
                stride=2,
                padding=1,
                output_padding=decoder_output_padding[0],
                bias=False,
            ),
            # Why isn't this DecoderLayer3D?
            torch.nn.Sigmoid(),
        )
    decoder_layers.append(last_layer)
    decoder = torch.nn.Sequential(*decoder_layers)

    return encoder, mu_layer, var_layer, decoder
