
import mlflow
import mlflow.keras
import tensorflow as tf
from pathlib import Path
from urllib.parse import urlparse
from chest_cancer_classifier.constants import *
from chest_cancer_classifier.utils.common_functions import read_yaml, create_directories, save_json
from src.chest_cancer_classifier.entity.config_entity import EvaluationConfig


class Evaluation:
    def __init__(self, config: EvaluationConfig):
        # Initialize the Evaluation class with the provided configuration
        self.config = config

    def _valid_generator(self):
        # Create a data generator for validation images with specific configurations
        datagenerator_kwargs = dict(
            rescale=1./255,  # Normalize pixel values to [0, 1]
            validation_split=0.30  # Use 30% of the data for validation
        )

        # Specify parameters for the data flow generator
        dataflow_kwargs = dict(
            target_size=self.config.params_image_size[:-1],  # Resize images to the target size, excluding the last dimension (channels)
            batch_size=self.config.params_batch_size,  # Set the batch size for loading images
            interpolation="bilinear"  # Use bilinear interpolation for resizing
        )

        # Create a Keras ImageDataGenerator for validation data
        valid_datagenerator = tf.keras.preprocessing.image.ImageDataGenerator(
            **datagenerator_kwargs
        )

        # Generate batches of validation data from the specified directory
        self.valid_generator = valid_datagenerator.flow_from_directory(
            directory=self.config.training_data,  # Directory containing validation images
            subset="validation",  # Specify that this is the validation subset
            shuffle=False,  # Do not shuffle the data
            class_mode="sparse",  # Set to "sparse" for integer labels
            **dataflow_kwargs  # Pass the data flow parameters
        )

    @staticmethod
    def load_model(path: Path) -> tf.keras.Model:
        # Load a Keras model from the specified path
        return tf.keras.models.load_model(path)

    def evaluation(self):
        # Load the model specified in the configuration
        self.model = self.load_model(self.config.path_of_model)

        # Recompile the model with binary_crossentropy to ensure correct configuration for binary classification
        self.model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
        
        # Create the validation data generator
        self._valid_generator()
        
        # Evaluate the model on the validation data
        self.score = self.model.evaluate(self.valid_generator)
        
        # Save the evaluation scores
        self.save_score()

    def save_score(self):
        # Save the evaluation scores (loss and accuracy) to a JSON file
        scores = {"loss": self.score[0], "accuracy": self.score[1]}
        save_json(path=Path("scores.json"), data=scores)

    def log_into_mlflow(self):
        # Set the MLflow tracking URI from the configuration
        mlflow.set_registry_uri(self.config.mlflow_uri)
        
        # Parse the tracking URI to determine the type of storage used
        tracking_url_type_store = urlparse(mlflow.get_tracking_uri()).scheme
        
        # Set the experiment name
        experiment_name = "Model Evaluation Experimentation" 
        mlflow.set_experiment(experiment_name)

        # Start a new MLflow run to log parameters and metrics
        with mlflow.start_run(run_name="Chest Cancer Classification"):
            # Log parameters from the configuration
            mlflow.log_params(self.config.all_params)
            # Log evaluation metrics (loss and accuracy)
            mlflow.log_metrics(
                {"loss": self.score[0], "accuracy": self.score[1]}
            )
            # Check if the tracking URL is not a file store
            if tracking_url_type_store != "file":
                # Register the model with MLflow
                mlflow.keras.log_model(self.model, "model", registered_model_name="VGG16Model")
                                
            else:
                # Log the model without registration if using file store
                mlflow.keras.log_model(self.model, "model")