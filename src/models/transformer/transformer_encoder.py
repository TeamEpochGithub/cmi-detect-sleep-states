import math
from torch import nn, Tensor

from src.models.transformer.utils import get_activation_fn
from .encoder import TransformerBatchNormEncoderLayer
from .positional_encoding import get_pos_encoder
from torch.nn.modules import TransformerEncoderLayer


class TSTransformerEncoderClassiregressor(nn.Module):
    """
    Simplest classifier/regressor. Can be either regressor or classifier because the output does not include
    softmax. Concatenates final layer embeddings and uses 0s to ignore padding embeddings in final output layer.

    Args:
        feat_dim: feature dimension
        max_len: maximum length of the input sequence
        d_model: the embed dim
        n_heads: the number of heads in the multihead attention models
        n_layers: the number of sub-encoder-layers in the encoder
        dim_feedforward: the dimension of the feedforward network model
        num_classes: the number of classes in the classification task
        dropout: the dropout value
        pos_encoding: positional encoding method
        activation: the activation function of intermediate layer, relu or gelu
        norm: the normalization layer
        freeze: whether to freeze the positional encoding layer
    """

    def __init__(
        self,
        feat_dim: int,
        max_len: int,
        d_model: int,
        n_heads: int,
        n_layers: int,
        dim_feedforward: int,
        num_classes: int,
        dropout: float = 0.1,
        pos_encoding: str = "fixed",
        activation: str = "gelu",
        norm: str = "BatchNorm",
        freeze: bool = False,
    ):
        super(TSTransformerEncoderClassiregressor, self).__init__()

        self.max_len = max_len
        self.d_model = d_model
        self.n_heads = n_heads

        self.project_inp = nn.Linear(feat_dim, d_model)
        self.pos_enc = get_pos_encoder(pos_encoding)(
            d_model, dropout=dropout * (1.0 - freeze), max_len=max_len
        )

        if norm == "LayerNorm":
            encoder_layer = TransformerEncoderLayer(
                d_model,
                self.n_heads,
                dim_feedforward,
                dropout * (1.0 - freeze),
                activation=activation,
            )
        else:
            encoder_layer = TransformerBatchNormEncoderLayer(
                d_model,
                self.n_heads,
                dim_feedforward,
                dropout * (1.0 - freeze),
                activation=activation,
            )

        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer, n_layers)

        self.act = get_activation_fn(activation)

        self.dropout1 = nn.Dropout(dropout)

        self.feat_dim = feat_dim
        self.num_classes = num_classes
        self.output_layer = self.build_output_module(
            d_model, max_len, num_classes)
        self.act_out = nn.ReLU()

    def build_output_module(
        self, d_model: int, max_len: int, num_classes: int
    ) -> nn.Module:
        """ Build linear layer that maps from d_model*max_len to num_classes.

        Softmax not included here as it is computed in the loss function.

        Args:
            d_model: the embed dim
            max_len: maximum length of the input sequence
            num_classes: the number of classes in the classification task

        Returns:
            output_layer: Tensor of shape (batch_size, num_classes)
        """
        output_layer = nn.Linear(d_model * max_len, num_classes)
        # no softmax (or log softmax), because CrossEntropyLoss does this internally. If probabilities are needed,
        # add F.log_softmax and use NLLoss
        return output_layer

    def forward(self, X: Tensor, padding_masks: Tensor) -> Tensor:
        """
        Args:
            X: (batch_size, seq_length, feat_dim) torch tensor of masked features (input)
            padding_masks: (batch_size, seq_length) boolean tensor, 1 means keep vector at this position, 0 means padding
        Returns:
            output: (batch_size, num_classes)
        """

        # permute because pytorch convention for transformers is [seq_length, batch_size, feat_dim]. padding_masks [batch_size, feat_dim]
        inp = X.permute(1, 0, 2)
        inp = self.project_inp(inp) * math.sqrt(
            self.d_model
        )  # [seq_length, batch_size, d_model] project input vectors to d_model dimensional space
        inp = self.pos_enc(inp)  # add positional encoding
        # NOTE: logic for padding masks is reversed to comply with definition in MultiHeadAttention, TransformerEncoderLayer
        output = self.transformer_encoder(
            inp, src_key_padding_mask=~padding_masks
        )  # (seq_length, batch_size, d_model)
        output = self.act(
            output
        )  # the output transformer encoder/decoder embeddings don't include non-linearity
        output = output.permute(1, 0, 2)  # (batch_size, seq_length, d_model)
        output = self.dropout1(output)

        # Output
        # zero-out padding embeddings
        output = output * padding_masks.unsqueeze(-1)
        output = output.reshape(
            output.shape[0], -1
        )  # (batch_size, seq_length * d_model)
        output = self.output_layer(output)  # (batch_size, num_classes)
        output = self.act_out(output)

        return output
