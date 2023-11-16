# This file does the training of the models
import torch

import wandb
from src import data_info
from src.configs.load_config import ConfigLoader
from src.logger.logger import logger
from src.util.hash_config import hash_config
from src.util.printing_utils import print_section_separator
from main_utils import train_from_config, full_train_from_config, scoring
from sweep import play_mp3


def main() -> None:
    """
    Main function for training the model
    :param config: loaded config
    """
    print_section_separator("Q1 - Detect Sleep States - Kaggle", spacing=0)
    logger.info("Start of main.py")

    # Load config file and hash
    global config_loader
    config_hash = hash_config(config_loader.get_config(), length=16)
    logger.info("Config hash encoding: " + config_hash)

    # Initialize wandb
    if config_loader.get_log_to_wandb():
        # Add models

        # Get the hpo config
        if config_loader.get_hpo():
            config_loader.config["hpo_model"] = config_loader.get_hpo_config(
            ).config

        # Initialize wandb
        wandb.init(
            project='detect-sleep-states',
            name=config_hash,
            config=config_loader.get_config()
        )
        if config_loader.get_hpo():

            # Merge the config from the hpo config
            config_loader.config |= wandb.config

            # Update the hpo config with the merged config
            config_loader.get_hpo_config().config = config_loader.config.get("hpo_model")

            # Update hash as the config is different now
            config_hash = hash_config(config_loader.get_config(), length=16)

            # Update the wandb summary with the updated config
            wandb.run.summary.update(config_loader.get_config())
            wandb.run.name = config_hash
        else:
            # Get the ensemble configs and add them to the config on wandb
            ensemble = config_loader.get_ensemble()
            models = ensemble.get_models()
            for i, model_config in enumerate(models):
                wandb.config[f"model_{i}"] = model_config.get_config()

        logger.info(f"Logging to wandb with run id: {config_hash}")
    else:
        logger.info("Not logging to wandb")

        if config_loader.get_hpo():
            logger.critical("HPO requires wandb")
            raise Exception("HPO requires wandb")

    # Predict with CPU
    pred_cpu = config_loader.get_pred_with_cpu()
    if pred_cpu:
        logger.info("Predicting with CPU for inference")
    else:
        logger.info("Predicting with GPU for inference")

    # ------------------------------------------- #
    #                 Ensemble                    #
    # ------------------------------------------- #

    # Initialize models
    store_location = config_loader.get_model_store_loc()
    logger.info("Model store location: " + store_location)

    # If hpo is enabled, run hpo instead
    # This can be done via terminal and a sweep or a local cross validation run
    if config_loader.get_hpo():
        logger.info("Running HPO")
        train_from_config(config_loader.get_hpo_config(),
                          config_loader, store_location, hpo=True)
        return

    # Initialize models
    logger.info("Initializing models...")
    ensemble = config_loader.get_ensemble()
    models = ensemble.get_models()
    if not ensemble.get_pred_only():
        for _, model_config in enumerate(models):
            train_from_config(model_config, config_loader,
                              store_location, hpo=False)
    else:
        logger.info("Not training models")

    # ------------------------------------------------------- #
    #                    Scoring                              #
    # ------------------------------------------------------- #

    print_section_separator("Scoring", spacing=0)
    data_info.stage = "scoring"
    data_info.substage = ""

    if config_loader.get_scoring():
        scoring(config=config_loader)
    else:
        logger.info("Not scoring")

    # ------------------------------------------------------- #
    #                    Train for submission                 #
    # ------------------------------------------------------- #

    print_section_separator("Train for submission", spacing=0)
    data_info.stage = "train for submission"

    if config_loader.get_train_for_submission():
        data_info.substage = "Full"
        for model_config in ensemble.get_models():
            config_loader.reset_globals()
            full_train_from_config(config_loader, model_config, store_location)
        logger.info("Retraining models for submission")
    else:
        logger.info("Not training best model for submission")

    # [optional] finish the wandb run, necessary in notebooks
    if config_loader.get_log_to_wandb():
        wandb.finish()
        logger.info("Finished logging to wandb")


if __name__ == "__main__":

    # Set up logging
    import coloredlogs
    coloredlogs.install()

    # Set seed for reproducibility
    torch.manual_seed(42)

    # Load config file
    config_loader: ConfigLoader = ConfigLoader("configs/2d-cnn-spectrogram.json")

    # Gotta sweep
    if config_loader.get_hpo():
        mp3_file_path = "gotta_sweep.mp3"  # Replace with the path to your MP3 file
        play_mp3(mp3_file_path)

    main()
