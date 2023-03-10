from keras.layers import Input, Dense, LSTM, multiply, concatenate, Activation, Masking, Reshape
from keras.layers import Dense, Dropout, Flatten, BatchNormalization, Input
from keras.layers import Conv1D, BatchNormalization, GlobalAveragePooling1D, Permute, Dropout
from keras.models import Sequential, Model
from sktime_dl.utils.layer_utils import AttentionLSTM

import numpy as np
import torch
import torchmetrics
from tqdm import tqdm


def squeeze_excite_block(input):
    ''' Create a squeeze-excite block
    Args:
        input: input tensor
        filters: number of output filters
        k: width factor
    Returns: a keras tensor
    '''
    filters = input.shape[-1]  # channel_axis = -1 for TF

    se = GlobalAveragePooling1D()(input)
    se = Reshape((1, filters))(se)
    se = Dense(filters // 16,  activation='relu',
               kernel_initializer='he_normal', use_bias=False)(se)
    se = Dense(filters, activation='sigmoid',
               kernel_initializer='he_normal', use_bias=False)(se)
    se = multiply([input, se])
    return se


def generate_model():
    ip = Input(shape=(1, 40))
    # stride = 10

    # x = Permute((2, 1))(ip)
    # x = Conv1D(MAX_NB_VARIABLES // stride, 8, strides=stride, padding='same', activation='relu', use_bias=False,
    #            kernel_initializer='he_uniform')(x)  # (None, variables / stride, timesteps)
    # x = Permute((2, 1))(x)

    # ip1 = K.reshape(ip,shape=(MAX_TIMESTEPS,

    # x = Permute((2, 1))(ip)
    x = Masking()(ip)
    x = AttentionLSTM(8)(x)
    x = Dropout(0.8)(x)

    y = Permute((2, 1))(ip)
    y = Conv1D(128, 8, padding='same', kernel_initializer='he_uniform')(y)
    y = BatchNormalization()(y)
    y = Activation('relu')(y)
    y = squeeze_excite_block(y)

    y = Conv1D(256, 5, padding='same', kernel_initializer='he_uniform')(y)
    y = BatchNormalization()(y)
    y = Activation('relu')(y)
    y = squeeze_excite_block(y)

    y = Conv1D(256, 5, padding='same', kernel_initializer='he_uniform')(y)
    y = BatchNormalization()(y)
    y = Activation('relu')(y)

    y = Conv1D(128, 3, padding='same', kernel_initializer='he_uniform')(y)
    y = BatchNormalization()(y)
    y = Activation('relu')(y)

    y = GlobalAveragePooling1D()(y)

    x = concatenate([x, y])

    # out1 = Dense(11,input_dim=11, kernel_initializer='he_uniform', activation='relu')(x)
    out = Dense(1, kernel_initializer='he_uniform')(x)
    model = Model(ip, out)
    model.compile(loss='mean_squared_error', optimizer='adam')
    model.summary()

    # add load model code here to fine-tune

    return model


def Return_Model():
    model_noise_resilience = generate_model()
    return model_noise_resilience


def Train_Model(model, matrix, sets_training, retraining, dataset):
    time_arr = []

    if retraining:
        model.load_weights(f"trained_models/dnn-{dataset}.h5")

    else:
        # IF TRAINING FOR THE FIRST TIME

        Y_train = np.zeros((matrix.shape[0]*len(sets_training), ))
        X_train = np.zeros((matrix.shape[0]*len(sets_training), 40))

        test = 0

        with torch.no_grad():  # disabled gradient calculation because were doing it manually
            mse = torchmetrics.MeanSquaredError()
            for num, i in tqdm(enumerate(sets_training)):
                pred = []
                samples = matrix[:, i:i+40]
                labels = matrix[:, i+40]
                # print(f"sample: {samples}, label:{labels}")
                # samples = samples.to(device) # pass sample and label (1 at a time)
                # labels = labels.to(device)

                for n in range(samples.shape[0]):
                    Y_train[test] = labels[n]
                    X_train[test] = samples[n, :]
                    test += 1

        X_train = X_train.reshape(X_train.shape[0], 1, X_train.shape[1])

        model.fit(X_train, Y_train, epochs=10, batch_size=128)

        model.save_weights(f"trained_models/dnn-{dataset}.h5")

    return model, time_arr


def Test_Model(model, matrix, sets_testing):

    dif_dnn = []

    with torch.no_grad():
        mse = torchmetrics.MeanSquaredError()
        for i in tqdm(sets_testing):
            pred = []
            samples = matrix[:, i:i+40]
            labels = matrix[:, i+40]
            for n in range(samples.shape[0]):
                sample = samples[n, :]
                sample2 = sample.reshape(1, 1, sample.shape[0])

                # Pass samples from test to model (forward function)
                predictions = model.predict(sample2)
                pred.append(predictions)

                mse.update(torch.tensor(
                    predictions[0, 0]), torch.tensor(labels[n]))

                dif_dnn.append(np.absolute(labels[n]-predictions))

    print(f"Testing mean squared error of {(mse.compute().item()):.3f}")

    return model, dif_dnn
