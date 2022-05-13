'''
brief: Reference_model
Author: Steffen Schotthöfer
Version: 0.0
Date 12.04.2022
'''
import tensorflow as tf
from tensorflow import keras
from os import path, makedirs
import numpy as np
from keras.engine.base_layer import Layer


#  Convolutional DLRANets

class DLRANetConv(keras.Model):

    def __init__(self, low_rank=20, tol=0.07, rmax_total=100, image_dims=(28, 28, 1), output_dim=10,
                 name="DLRANetConv",
                 **kwargs):
        super(DLRANetConv, self).__init__(name=name, **kwargs)
        # dlra_layer_dim = 250
        self.image_dims = image_dims
        self.output_dim = output_dim

        self.low_rank = low_rank
        self.tol = tol
        self.rmax_total = rmax_total

        # architecture
        self.dlraBlockInput = DLRALayerConv(low_rank=self.low_rank, epsAdapt=self.tol, rmax_total=self.rmax_total,
                                            stride=(1, 1), rate=(1, 1), size=(5, 5), filters=6,
                                            image_dims=image_dims)
        self.avgPooling1 = keras.layers.AveragePooling2D(pool_size=(2, 2))
        next_image_dims = self.dlraBlockInput.output_shape_conv
        self.dlraBlock1 = DLRALayerConv(low_rank=self.low_rank, epsAdapt=self.tol, rmax_total=self.rmax_total,
                                        stride=(1, 1), rate=(1, 1), size=(5, 5), filters=16,
                                        image_dims=next_image_dims)
        self.avgPooling2 = keras.layers.AveragePooling2D(pool_size=(2, 2))
        next_image_dims = self.dlraBlock1.output_shape_conv
        self.dlraBlock2 = DLRALayerConv(low_rank=self.low_rank, epsAdapt=self.tol, rmax_total=self.rmax_total,
                                        stride=(5, 5), rate=(2, 2), size=(5, 5), filters=120,
                                        image_dims=next_image_dims)
        self.flatten = keras.layers.Flatten()
        self.dlraBlock3 = DLRALayer(input_dim=self.dlra_layer_dim, units=self.dlra_layer_dim, low_rank=self.low_rank,
                                    epsAdapt=self.tol,
                                    rmax_total=rmax_total, )
        self.dlraBlock4 = DLRALayer(input_dim=84, units=self.dlra_layer_dim, low_rank=self.low_rank,
                                    epsAdapt=self.tol,
                                    rmax_total=rmax_total, )
        self.dlraBlockOutput = Linear(input_dim=next_image_dims[-1], units=self.output_dim)

    def build_model(self):
        self.dlraBlockInput.build_model()
        self.dlraBlock1.build_model()
        self.dlraBlock2.build_model()
        self.dlraBlock3.build_model()
        return 0

    # @tf.function
    def call(self, inputs, step: int = 0):
        z = self.dlraBlockInput(inputs, step=step)
        z = self.avgPooling1(z)
        z = tf.keras.activations.sigmoid(z)
        z = self.dlraBlock1(z, step=step)
        z = self.avgPooling2(z)
        z = tf.keras.activations.sigmoid(z)
        z = self.dlraBlock2(z, step=step)
        z = self.flatten(z)
        z = self.dlraBlock3(z, step=step)
        z = self.dlraBlock4(z, step=step)
        z = self.dlraBlockOutput(z)
        return z

    @staticmethod
    def set_none_grads_to_zero(grads, weights):
        """
        :param grads: gradients of current tape
        :param weights: weights of current model
        :return: sets the nonexistent gradients to zero (i K step, the grads of S and L step are None, which throws annoying warnings)
        """
        for i in range(len(grads)):
            if grads[i] is None:
                grads[i] = tf.zeros(shape=weights[i].shape, dtype=tf.float32)
        return 0

    @staticmethod
    def set_dlra_bias_grads_to_zero(grads):
        """
        :param grads: gradients of current tape
        :return: sets the nonexistent gradients to zero (i K step, the grads of S and L step are None, which throws annoying warnings)
        """
        for i in range(len(grads)):
            if len(grads[i].shape) == 1:
                grads[i] = tf.math.scalar_mul(0.0, grads[i])
        return 0

    def toggle_non_s_step_training(self):
        # self.layers[0].trainable = False  # Dense input
        self.layers[-1].trainable = False  # Dense output

        return 0

    def toggle_s_step_training(self):
        # self.layers[0].trainable = True  # Dense input
        self.layers[-1].trainable = True  # Dense output
        return 0

    def save(self, folder_name):
        self.dlraBlockInput.save(folder_name=folder_name, layer_id=0)
        self.dlraBlock1.save(folder_name=folder_name, layer_id=1)
        self.dlraBlock2.save(folder_name=folder_name, layer_id=2)
        self.dlraBlock3.save(folder_name=folder_name, layer_id=3)
        self.dlraBlockOutput.save(folder_name=folder_name)
        return 0

    def load(self, folder_name):
        self.dlraBlockInput.load(folder_name=folder_name, layer_id=0)
        self.dlraBlock1.load(folder_name=folder_name, layer_id=1)
        self.dlraBlock2.load(folder_name=folder_name, layer_id=2)
        self.dlraBlock3.load(folder_name=folder_name, layer_id=3)
        self.dlraBlockOutput.load(folder_name=folder_name)
        return 0


class Linear(keras.layers.Layer):
    def __init__(self, units=32, input_dim=32, name="linear", **kwargs):
        super(Linear, self).__init__(**kwargs)
        self.units = units
        self.w = self.add_weight(shape=(input_dim, units), initializer="random_normal",
                                 trainable=True, )
        self.b = self.add_weight(shape=(self.units,), initializer="random_normal", trainable=True)

    def call(self, inputs):
        return tf.matmul(inputs, self.w) + self.b

    def get_config(self):
        config = super(Linear, self).get_config()
        config.update({"units": self.units})
        return config

    def save(self, folder_name):
        w_np = self.w.numpy()
        np.save(folder_name + "/w_out.npy", w_np)
        b_np = self.b.numpy()
        np.save(folder_name + "/b_out.npy", b_np)
        return 0

    def load(self, folder_name):
        a_np = np.load(folder_name + "/w_out.npy")
        self.w = tf.Variable(initial_value=a_np,
                             trainable=True, name="w_", dtype=tf.float32)
        b_np = np.load(folder_name + "/b_out.npy")
        self.b1 = tf.Variable(initial_value=b_np,
                              trainable=True, name="b_", dtype=tf.float32)


# Layers-----

class DLRALayerConv(keras.layers.Layer):
    def __init__(self, low_rank=10, epsAdapt=0.1, rmax_total=100, stride: tuple = (5, 5), rate: tuple = (2, 2),
                 size: tuple = (3, 3), filters=10, image_dims=(28, 28, 1), name="dlra_block_Conv2D",
                 **kwargs):
        super(DLRALayerConv, self).__init__(**kwargs)
        # DLRA options
        self.epsAdapt = epsAdapt  # for unconventional integrator
        self.low_rank = low_rank
        self.rmax_total = rmax_total

        # Convolution options
        self.stride = stride
        self.rate = rate
        self.filters = filters
        self.channels = image_dims[2]
        self.size = size
        self.image_dims = image_dims
        # Resulting shapes
        self.units = self.filters  # output dimension
        self.input_dim = self.size[0] * self.size[1] * self.channels

        # Compute output patch shape
        batch_size = 4
        test_imgs = tf.ones(shape=(batch_size, image_dims[0], image_dims[1], image_dims[2]))

        patches = tf.image.extract_patches(images=test_imgs,
                                           sizes=[1, self.size[0], self.size[1], 1],
                                           strides=[1, self.stride[0], self.stride[1], 1],
                                           rates=[1, self.rate[0], self.rate[1], 1],
                                           padding='VALID')
        # patches dim: (batch,row,col,L), where L  = size[0]xsize[1]xC_in = self.input_dim
        # output dims are rowxcolxfilters
        print("Image patches for conv layer")
        print(patches.shape)
        # sanity check
        W = tf.ones(shape=(self.input_dim, self.filters))
        out = tf.tensordot(patches, W, axes=([-1], [0]))
        print(out.shape)
        self.output_shape_conv = (out.shape[1], out.shape[2], out.shape[3])
        print("Sanity check for conv layer passed")

    def build_model(self):

        self.k = self.add_weight(shape=(self.input_dim, self.low_rank), initializer="random_normal",
                                 trainable=True, name="k_")
        self.l_t = self.add_weight(shape=(self.low_rank, self.units), initializer="random_normal",
                                   trainable=True, name="lt_")
        self.s = self.add_weight(shape=(self.low_rank, self.low_rank), initializer="random_normal",
                                 trainable=True, name="s_")
        self.b = self.add_weight(shape=self.output_shape_conv, initializer="random_normal", trainable=True, name="b_")
        # auxiliary variables
        self.aux_U = self.add_weight(shape=(self.input_dim, self.low_rank), initializer="random_normal",
                                     trainable=False, name="aux_U")
        self.aux_Unp1 = self.add_weight(shape=(self.input_dim, self.low_rank), initializer="random_normal",
                                        trainable=False, name="aux_Unp1")
        self.aux_Vt = self.add_weight(shape=(self.low_rank, self.units), initializer="random_normal",
                                      trainable=False, name="Vt")
        self.aux_Vtnp1 = self.add_weight(shape=(self.low_rank, self.units), initializer="random_normal",
                                         trainable=False, name="vtnp1")
        self.aux_N = self.add_weight(shape=(self.low_rank, self.low_rank), initializer="random_normal",
                                     trainable=False, name="aux_N")
        self.aux_M = self.add_weight(shape=(self.low_rank, self.low_rank), initializer="random_normal",
                                     trainable=False, name="aux_M")
        # Todo: initializer with low rank
        return 0

    # @tf.function
    def call(self, inputs, step: int = 0):
        """
        :param inputs: layer input
        :param step: step conter: k:= 0, l:=1, s:=2
        :return:
        """
        # Convert Input in Patched Convolution
        patches = tf.image.extract_patches(images=inputs,
                                           sizes=[1, self.size[0], self.size[1], 1],
                                           strides=[1, self.stride[0], self.stride[1], 1],
                                           rates=[1, self.rate[0], self.rate[1], 1],
                                           padding='VALID')

        if step == 0:  # k-step
            z = tf.tensordot(patches, self.k, axes=([-1], [0]))
            z = tf.tensordot(z, self.aux_Vt, axes=([-1], [0]))
            # z = tf.matmul(tf.matmul(inputs, self.k), self.aux_Vt)
        elif step == 1:  # l-step
            z = tf.tensordot(patches, self.aux_U, axes=([-1], [0]))
            z = tf.tensordot(z, self.l_t, axes=([-1], [0]))
            # z = tf.matmul(tf.matmul(inputs, self.aux_U), self.l_t)
        else:  # s-step
            z = tf.tensordot(patches, self.aux_Unp1, axes=([-1], [0]))
            z = tf.tensordot(z, self.s, axes=([-1], [0]))
            z = tf.tensordot(z, self.aux_Vtnp1, axes=([-1], [0]))
            # z = tf.matmul(tf.matmul(tf.matmul(inputs, self.aux_Unp1), self.s), self.aux_Vtnp1)
        return tf.keras.activations.tanh(z + self.b)

    @tf.function
    def k_step_preprocessing(self, ):
        k = tf.matmul(self.aux_U, self.s)
        self.k.assign(k)  # = tf.Variable(initial_value=k, trainable=True, name="k_")
        return 0

    @tf.function
    def k_step_postprocessing(self):
        aux_Unp1, _ = tf.linalg.qr(self.k)
        self.aux_Unp1.assign(aux_Unp1)  # = tf.Variable(initial_value=aux_Unp1, trainable=False, name="aux_Unp1")
        N = tf.matmul(tf.transpose(self.aux_Unp1), self.aux_U)
        self.aux_N.assign(N)
        return 0

    def k_step_postprocessing_adapt(self):
        aux_Unp1, _ = tf.linalg.qr(tf.concat((self.k, self.aux_U), axis=1))
        self.aux_Unp1 = tf.Variable(initial_value=aux_Unp1, trainable=False, name="aux_Unp1")
        self.aux_N = tf.matmul(tf.transpose(self.aux_Unp1), self.aux_U)
        return 0

    @tf.function
    def l_step_preprocessing(self, ):
        l_t = tf.matmul(self.s, self.aux_Vt)
        self.l_t.assign(l_t)  # = tf.Variable(initial_value=l_t, trainable=True, name="lt_")
        return 0

    @tf.function
    def l_step_postprocessing(self):
        aux_Vtnp1, _ = tf.linalg.qr(tf.transpose(self.l_t))
        self.aux_Vtnp1.assign(tf.transpose(aux_Vtnp1))
        M = tf.matmul(self.aux_Vtnp1, tf.transpose(self.aux_Vt))
        self.aux_M.assign(M)
        return 0

    def l_step_postprocessing_adapt(self):
        aux_Vtnp1, _ = tf.linalg.qr(tf.concat((tf.transpose(self.l_t), tf.transpose(self.aux_Vt)), axis=1))
        self.aux_Vtnp1 = tf.transpose(aux_Vtnp1)
        self.aux_M = tf.matmul(self.aux_Vtnp1, tf.transpose(self.aux_Vt))
        return 0

    @tf.function
    def s_step_preprocessing(self):
        self.aux_U.assign(self.aux_Unp1)
        self.aux_Vt.assign(self.aux_Vtnp1)
        s = tf.matmul(tf.matmul(self.aux_N, self.s), tf.transpose(self.aux_M))
        self.s.assign(s)  # = tf.Variable(initial_value=s, trainable=True, name="s_")
        return 0

    def rank_adaption(self):
        # 1) compute SVD of S
        d, u2, v2 = tf.linalg.svd(self.s)  # d=singular values, u2 = left singuar vecs, v2= right singular vecss
        # print(d.shape)
        tmp = 0.0
        tol = self.epsAdapt * tf.linalg.norm(d)  # absolute value treshold (try also relative one)
        rmax = int(tf.floor(d.shape[0] / 2))
        for j in range(0, 2 * rmax - 1):
            tmp = tf.linalg.norm(d[j:2 * rmax - 1])
            if tmp < tol:
                rmax = j
                break

        rmax = tf.minimum(rmax, self.rmax_total)
        rmax = tf.maximum(rmax, 2)

        # update s
        self.s = tf.linalg.tensor_diag(d[:rmax])
        # self.s = s

        # update u and v
        self.aux_U = tf.matmul(self.aux_U, u2[:, :rmax])
        self.aux_Vt = tf.matmul(v2[:rmax, :], self.aux_Vt)
        self.low_rank = rmax
        return 0

    def get_config(self):
        config = super(DLRALayerConv, self).get_config()
        config.update({"units": self.units})
        config.update({"low_rank": self.low_rank})
        return config

    def save(self, folder_name, layer_id):
        # main_variables
        k_np = self.k.numpy()
        np.save(folder_name + "/k" + str(layer_id) + ".npy", k_np)
        l_t_np = self.l_t.numpy()
        np.save(folder_name + "/l_t" + str(layer_id) + ".npy", l_t_np)
        s_np = self.s.numpy()
        np.save(folder_name + "/s" + str(layer_id) + ".npy", s_np)
        b_np = self.b.numpy()
        np.save(folder_name + "/b" + str(layer_id) + ".npy", b_np)
        # aux_variables
        aux_U_np = self.aux_U.numpy()
        np.save(folder_name + "/aux_U" + str(layer_id) + ".npy", aux_U_np)
        aux_Unp1_np = self.aux_Unp1.numpy()
        np.save(folder_name + "/aux_Unp1" + str(layer_id) + ".npy", aux_Unp1_np)
        aux_Vt_np = self.aux_Vt.numpy()
        np.save(folder_name + "/aux_Vt" + str(layer_id) + ".npy", aux_Vt_np)
        aux_Vtnp1_np = self.aux_Vtnp1.numpy()
        np.save(folder_name + "/aux_Vtnp1" + str(layer_id) + ".npy", aux_Vtnp1_np)
        aux_N_np = self.aux_N.numpy()
        np.save(folder_name + "/aux_N" + str(layer_id) + ".npy", aux_N_np)
        aux_M_np = self.aux_M.numpy()
        np.save(folder_name + "/aux_M" + str(layer_id) + ".npy", aux_M_np)
        return 0

    def load(self, folder_name, layer_id):

        # main variables
        k_np = np.load(folder_name + "/k" + str(layer_id) + ".npy")
        self.low_rank = k_np.shape[1]
        self.k = tf.Variable(initial_value=k_np,
                             trainable=True, name="k_", dtype=tf.float32)
        l_t_np = np.load(folder_name + "/l_t" + str(layer_id) + ".npy")
        self.l_t = tf.Variable(initial_value=l_t_np,
                               trainable=True, name="lt_", dtype=tf.float32)
        s_np = np.load(folder_name + "/s" + str(layer_id) + ".npy")
        self.s = tf.Variable(initial_value=s_np,
                             trainable=True, name="s_", dtype=tf.float32)
        # aux variables
        aux_U_np = np.load(folder_name + "/aux_U" + str(layer_id) + ".npy")
        self.aux_U = tf.Variable(initial_value=aux_U_np,
                                 trainable=True, name="aux_U", dtype=tf.float32)
        aux_Unp1_np = np.load(folder_name + "/aux_Unp1" + str(layer_id) + ".npy")
        self.aux_Unp1 = tf.Variable(initial_value=aux_Unp1_np,
                                    trainable=True, name="aux_Unp1", dtype=tf.float32)
        Vt_np = np.load(folder_name + "/aux_Vt" + str(layer_id) + ".npy")
        self.aux_Vt = tf.Variable(initial_value=Vt_np,
                                  trainable=True, name="Vt", dtype=tf.float32)
        vtnp1_np = np.load(folder_name + "/aux_Vtnp1" + str(layer_id) + ".npy")
        self.aux_Vtnp1 = tf.Variable(initial_value=vtnp1_np,
                                     trainable=True, name="vtnp1", dtype=tf.float32)
        aux_N_np = np.load(folder_name + "/aux_N" + str(layer_id) + ".npy")
        self.aux_N = tf.Variable(initial_value=aux_N_np,
                                 trainable=True, name="aux_N", dtype=tf.float32)
        aux_M_np = np.load(folder_name + "/aux_M" + str(layer_id) + ".npy")
        self.aux_M = tf.Variable(initial_value=aux_M_np,
                                 trainable=True, name="aux_M", dtype=tf.float32)
        return 0


class DLRALayer(keras.layers.Layer):
    def __init__(self, input_dim: int, units=32, low_rank=10, epsAdapt=0.1, rmax_total=100, name="dlra_block",
                 **kwargs):
        super(DLRALayer, self).__init__(**kwargs)
        self.epsAdapt = epsAdapt  # for unconventional integrator
        self.units = units
        self.low_rank = low_rank
        self.rmax_total = rmax_total
        self.input_dim = input_dim

    def build_model(self):

        self.k = self.add_weight(shape=(self.input_dim, self.low_rank), initializer="random_normal",
                                 trainable=True, name="k_")
        self.l_t = self.add_weight(shape=(self.low_rank, self.units), initializer="random_normal",
                                   trainable=True, name="lt_")
        self.s = self.add_weight(shape=(self.low_rank, self.low_rank), initializer="random_normal",
                                 trainable=True, name="s_")
        self.b = self.add_weight(shape=(self.units,), initializer="random_normal", trainable=True, name="b_")
        # auxiliary variables
        self.aux_U = self.add_weight(shape=(self.input_dim, self.low_rank), initializer="random_normal",
                                     trainable=False, name="aux_U")
        self.aux_Unp1 = self.add_weight(shape=(self.input_dim, self.low_rank), initializer="random_normal",
                                        trainable=False, name="aux_Unp1")
        self.aux_Vt = self.add_weight(shape=(self.low_rank, self.units), initializer="random_normal",
                                      trainable=False, name="Vt")
        self.aux_Vtnp1 = self.add_weight(shape=(self.low_rank, self.units), initializer="random_normal",
                                         trainable=False, name="vtnp1")
        self.aux_N = self.add_weight(shape=(self.low_rank, self.low_rank), initializer="random_normal",
                                     trainable=False, name="aux_N")
        self.aux_M = self.add_weight(shape=(self.low_rank, self.low_rank), initializer="random_normal",
                                     trainable=False, name="aux_M")
        # Todo: initializer with low rank
        return 0

    @tf.function
    def call(self, inputs, step: int = 0):
        """
        :param inputs: layer input
        :param step: step conter: k:= 0, l:=1, s:=2
        :return:
        """

        if step == 0:  # k-step
            z = tf.matmul(tf.matmul(inputs, self.k), self.aux_Vt)
        elif step == 1:  # l-step
            z = tf.matmul(tf.matmul(inputs, self.aux_U), self.l_t)
        else:  # s-step
            z = tf.matmul(tf.matmul(tf.matmul(inputs, self.aux_Unp1), self.s), self.aux_Vtnp1)
        return tf.keras.activations.relu(z + self.b)

    @tf.function
    def call(self, inputs, step: int = 0):
        """
        :param inputs: layer input
        :param step: step conter: k:= 0, l:=1, s:=2
        :return:
        """
        if step == 0:  # k-step
            z = tf.matmul(tf.matmul(inputs, self.k), self.aux_Vt)
        elif step == 1:  # l-step
            z = tf.matmul(tf.matmul(inputs, self.aux_U), self.l_t)
        else:  # s-step
            z = tf.matmul(tf.matmul(tf.matmul(inputs, self.aux_Unp1), self.s), self.aux_Vtnp1)
        return tf.keras.activations.relu(z + self.b)

    @tf.function
    def k_step_preprocessing(self, ):
        k = tf.matmul(self.aux_U, self.s)
        self.k.assign(k)  # = tf.Variable(initial_value=k, trainable=True, name="k_")
        return 0

    @tf.function
    def k_step_postprocessing(self):
        aux_Unp1, _ = tf.linalg.qr(self.k)
        self.aux_Unp1.assign(aux_Unp1)  # = tf.Variable(initial_value=aux_Unp1, trainable=False, name="aux_Unp1")
        N = tf.matmul(tf.transpose(self.aux_Unp1), self.aux_U)
        self.aux_N.assign(N)
        return 0

    def k_step_postprocessing_adapt(self):
        aux_Unp1, _ = tf.linalg.qr(tf.concat((self.k, self.aux_U), axis=1))
        self.aux_Unp1 = tf.Variable(initial_value=aux_Unp1, trainable=False, name="aux_Unp1")
        self.aux_N = tf.matmul(tf.transpose(self.aux_Unp1), self.aux_U)
        return 0

    @tf.function
    def l_step_preprocessing(self, ):
        l_t = tf.matmul(self.s, self.aux_Vt)
        self.l_t.assign(l_t)  # = tf.Variable(initial_value=l_t, trainable=True, name="lt_")
        return 0

    @tf.function
    def l_step_postprocessing(self):
        aux_Vtnp1, _ = tf.linalg.qr(tf.transpose(self.l_t))
        self.aux_Vtnp1.assign(tf.transpose(aux_Vtnp1))
        M = tf.matmul(self.aux_Vtnp1, tf.transpose(self.aux_Vt))
        self.aux_M.assign(M)
        return 0

    def l_step_postprocessing_adapt(self):
        aux_Vtnp1, _ = tf.linalg.qr(tf.concat((tf.transpose(self.l_t), tf.transpose(self.aux_Vt)), axis=1))
        self.aux_Vtnp1 = tf.transpose(aux_Vtnp1)
        self.aux_M = tf.matmul(self.aux_Vtnp1, tf.transpose(self.aux_Vt))
        return 0

    @tf.function
    def s_step_preprocessing(self):
        self.aux_U.assign(self.aux_Unp1)
        self.aux_Vt.assign(self.aux_Vtnp1)
        s = tf.matmul(tf.matmul(self.aux_N, self.s), tf.transpose(self.aux_M))
        self.s.assign(s)  # = tf.Variable(initial_value=s, trainable=True, name="s_")
        return 0

    def rank_adaption(self):
        # 1) compute SVD of S
        d, u2, v2 = tf.linalg.svd(self.s)  # d=singular values, u2 = left singuar vecs, v2= right singular vecss
        # print(d.shape)
        tmp = 0.0
        tol = self.epsAdapt * tf.linalg.norm(d)  # absolute value treshold (try also relative one)
        rmax = int(tf.floor(d.shape[0] / 2))
        for j in range(0, 2 * rmax - 1):
            tmp = tf.linalg.norm(d[j:2 * rmax - 1])
            if tmp < tol:
                rmax = j
                break

        rmax = tf.minimum(rmax, self.rmax_total)
        rmax = tf.maximum(rmax, 2)

        # update s
        self.s = tf.linalg.tensor_diag(d[:rmax])
        # self.s = s

        # update u and v
        self.aux_U = tf.matmul(self.aux_U, u2[:, :rmax])
        self.aux_Vt = tf.matmul(v2[:rmax, :], self.aux_Vt)
        self.low_rank = rmax
        return 0

    def get_config(self):
        config = super(DLRALayer, self).get_config()
        config.update({"units": self.units})
        config.update({"low_rank": self.low_rank})
        return config

    def save(self, folder_name, layer_id):
        # main_variables
        k_np = self.k.numpy()
        np.save(folder_name + "/k" + str(layer_id) + ".npy", k_np)
        l_t_np = self.l_t.numpy()
        np.save(folder_name + "/l_t" + str(layer_id) + ".npy", l_t_np)
        s_np = self.s.numpy()
        np.save(folder_name + "/s" + str(layer_id) + ".npy", s_np)
        b_np = self.b.numpy()
        np.save(folder_name + "/b" + str(layer_id) + ".npy", b_np)
        # aux_variables
        aux_U_np = self.aux_U.numpy()
        np.save(folder_name + "/aux_U" + str(layer_id) + ".npy", aux_U_np)
        aux_Unp1_np = self.aux_Unp1.numpy()
        np.save(folder_name + "/aux_Unp1" + str(layer_id) + ".npy", aux_Unp1_np)
        aux_Vt_np = self.aux_Vt.numpy()
        np.save(folder_name + "/aux_Vt" + str(layer_id) + ".npy", aux_Vt_np)
        aux_Vtnp1_np = self.aux_Vtnp1.numpy()
        np.save(folder_name + "/aux_Vtnp1" + str(layer_id) + ".npy", aux_Vtnp1_np)
        aux_N_np = self.aux_N.numpy()
        np.save(folder_name + "/aux_N" + str(layer_id) + ".npy", aux_N_np)
        aux_M_np = self.aux_M.numpy()
        np.save(folder_name + "/aux_M" + str(layer_id) + ".npy", aux_M_np)
        return 0

    def load(self, folder_name, layer_id):

        # main variables
        k_np = np.load(folder_name + "/k" + str(layer_id) + ".npy")
        self.low_rank = k_np.shape[1]
        self.k = tf.Variable(initial_value=k_np,
                             trainable=True, name="k_", dtype=tf.float32)
        l_t_np = np.load(folder_name + "/l_t" + str(layer_id) + ".npy")
        self.l_t = tf.Variable(initial_value=l_t_np,
                               trainable=True, name="lt_", dtype=tf.float32)
        s_np = np.load(folder_name + "/s" + str(layer_id) + ".npy")
        self.s = tf.Variable(initial_value=s_np,
                             trainable=True, name="s_", dtype=tf.float32)
        # aux variables
        aux_U_np = np.load(folder_name + "/aux_U" + str(layer_id) + ".npy")
        self.aux_U = tf.Variable(initial_value=aux_U_np,
                                 trainable=True, name="aux_U", dtype=tf.float32)
        aux_Unp1_np = np.load(folder_name + "/aux_Unp1" + str(layer_id) + ".npy")
        self.aux_Unp1 = tf.Variable(initial_value=aux_Unp1_np,
                                    trainable=True, name="aux_Unp1", dtype=tf.float32)
        Vt_np = np.load(folder_name + "/aux_Vt" + str(layer_id) + ".npy")
        self.aux_Vt = tf.Variable(initial_value=Vt_np,
                                  trainable=True, name="Vt", dtype=tf.float32)
        vtnp1_np = np.load(folder_name + "/aux_Vtnp1" + str(layer_id) + ".npy")
        self.aux_Vtnp1 = tf.Variable(initial_value=vtnp1_np,
                                     trainable=True, name="vtnp1", dtype=tf.float32)
        aux_N_np = np.load(folder_name + "/aux_N" + str(layer_id) + ".npy")
        self.aux_N = tf.Variable(initial_value=aux_N_np,
                                 trainable=True, name="aux_N", dtype=tf.float32)
        aux_M_np = np.load(folder_name + "/aux_M" + str(layer_id) + ".npy")
        self.aux_M = tf.Variable(initial_value=aux_M_np,
                                 trainable=True, name="aux_M", dtype=tf.float32)
        return 0


# Reference work

class ReferenceNet(keras.Model):

    def __init__(self, input_dim=10, output_dim=1, layer_dim=200, name="referenceNet", **kwargs):
        super(ReferenceNet, self).__init__(name=name, **kwargs)
        self.layer1 = Linear(units=layer_dim, input_dim=input_dim)
        self.layer2 = Linear(units=layer_dim, input_dim=layer_dim)
        self.layer3 = Linear(units=layer_dim, input_dim=layer_dim)
        self.layer4 = Linear(units=layer_dim, input_dim=layer_dim)
        self.layer5 = Linear(units=output_dim, input_dim=layer_dim)

    @tf.function
    def call(self, inputs):
        z = self.layer1(inputs)
        z = tf.keras.activations.relu(z)
        z = self.layer2(z)
        z = tf.keras.activations.relu(z)
        z = self.layer3(z)
        z = tf.keras.activations.relu(z)
        z = self.layer4(z)
        z = tf.keras.activations.relu(z)
        z = self.layer5(z)
        return z


# ------ utils below

def create_csv_logger_cb(folder_name: str):
    '''
    dynamically creates a csvlogger and tensorboard logger
    '''
    # check if dir exists
    if not path.exists(folder_name + '/historyLogs/'):
        makedirs(folder_name + '/historyLogs/')

    # checkfirst, if history file exists.
    logName = folder_name + '/historyLogs/history_001_'
    count = 1
    while path.isfile(logName + '.csv'):
        count += 1
        logName = folder_name + \
                  '/historyLogs/history_' + str(count).zfill(3) + '_'

    logFileName = logName + '.csv'
    # create logger callback
    f = open(logFileName, "a")

    return f, logFileName