from clinicadl.utils.network.pythae.pythae_utils import BasePythae


class pythae_Adversarial_AE(BasePythae):
    def __init__(
        self,
        encoder_decoder_config,
        adversarial_loss_scale,
        gpu=False,
    ):
        from pythae.models import Adversarial_AE, Adversarial_AE_Config

        encoder, decoder = super(pythae_Adversarial_AE, self).__init__(
            encoder_decoder_config = encoder_decoder_config,
            gpu=gpu,
        )

        model_config = Adversarial_AE_Config(
            input_dim=self.input_size,
            latent_dim=self.latent_space_size,
            adversarial_loss_scale=adversarial_loss_scale,
        )
        self.model = Adversarial_AE(
            model_config=model_config,
            encoder=encoder,
            decoder=decoder,
        )

    def get_trainer_config(self, output_dir, num_epochs, learning_rate, batch_size, optimizer):
        from pythae.trainers import AdversarialTrainerConfig

        return AdversarialTrainerConfig(
            output_dir=output_dir,
            num_epochs=num_epochs,
            learning_rate=learning_rate,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            optimizer_cls=optimizer,
        )
