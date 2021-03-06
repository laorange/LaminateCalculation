import json
from typing import Union, List
from pprint import pprint

from pydantic import BaseModel, Field
import numpy as np
from numpy import pi

Number = Union[float, int]


def frac(number: Number):
    return 1 / number


def input_a_number(help_text: str = "请输入一个数字", is_int: bool = False) -> Number:
    while 1:
        number = input(help_text + ": ")
        try:
            result = int(number) if is_int else float(number)
            print()
            return result
        except ValueError as e:
            print(e)
            print("您的输入不正确，请重新输入")


def input_a_number_list(help_text: str = "现在请输入一串数字", max_length: int = 1) -> List[Number]:
    ls: List[Number] = []
    print(f"{help_text}, 共需要输入{max_length}个数")
    while 1:
        if len(ls) == max_length:
            return ls
        ls.append(input_a_number(f"现在，请输入第{len(ls) + 1}个数"))


def transform_all_ndarray_attributes_of_obj_to_list(obj):
    for key, value in obj.__dict__.items():
        if isinstance(value, np.ndarray):
            obj.__setattr__(key, value.tolist())


class LayerInfo(BaseModel):
    E_l: Number
    E_t: Number
    G_lt: Number
    nu_lt: Number
    theta: Number
    thickness: Number


class LayerOnCoordinateLT:
    def __init__(self, E_l: Number, E_t: Number, nu_lt: Number, G_lt: Number):
        super().__init__()
        self.E_l = E_l
        self.E_t = E_t
        self.G_lt = G_lt
        self.nu_lt = nu_lt
        self.nu_tl = nu_lt * E_t / E_l

        self.souplesse_matrix_on_coordinate_L_T = np.array([
            [frac(self.E_l), - self.nu_lt / self.E_l, 0],
            [- self.nu_lt / self.E_l, frac(self.E_t), 0],
            [0, 0, frac(self.G_lt)]
        ])

    def updateWithTheta(self, theta):
        return LayerOnCoordinateXY(self.E_l, self.E_t, self.nu_lt, self.G_lt, theta)


class LayerOnCoordinateXY(LayerOnCoordinateLT):
    def __init__(self, E_l: Number, E_t: Number, nu_lt: Number, G_lt: Number, theta: Number):
        super(LayerOnCoordinateXY, self).__init__(E_l, E_t, nu_lt, G_lt)

        self.theta = theta
        c = self.cos_theta = np.cos(self.theta)
        s = self.sin_theta = np.sin(self.theta)

        hat_E_l = self.hat_E_l = self.E_l / (1 - self.nu_lt * self.nu_tl)
        hat_E_t = self.hat_E_t = self.E_t / (1 - self.nu_lt * self.nu_tl)
        nu_tl = self.nu_tl

        self.E_x = E_x = 1 / (c ** 4 / E_l + s ** 4 / E_t + (c * s) ** 2 * (frac(G_lt) - 2 * nu_lt / E_l))
        self.E_y = E_y = 1 / (s ** 4 / E_l + c ** 4 / E_t + (c * s) ** 2 * (frac(G_lt) - 2 * nu_lt / E_l))
        self.G_xy = G_xy = 1 / ((4 * (c * s) ** 2) * (frac(E_l) + frac(E_t) + 2 * nu_lt / E_l) + (c ** 2 - s ** 2) ** 2 / G_lt)
        self.mu_yx = mu_yx = (nu_lt / E_l * (c ** 4 + s ** 4) - (c * s) ** 2 * (frac(E_l) + frac(E_t) - frac(G_lt))) * E_y
        self.eta_xy = eta_xy = -2 * c * s * (c ** 2 / E_l - s ** 2 / E_t + (c ** 2 - s ** 2) * (nu_lt / E_l - 0.5 * frac(G_lt))) * G_xy
        self.mu_xy = mu_xy = -2 * c * s * (s ** 2 / E_l - c ** 2 / E_t + (c ** 2 - s ** 2) * (nu_lt / E_l - 0.5 * frac(G_lt))) * G_xy

        self.souplesse_matrix_on_coordinate_X_Y = np.array([
            [frac(E_x), -mu_yx / E_y, eta_xy / G_xy],
            [-mu_yx / E_y, frac(E_y), mu_xy / G_xy],
            [eta_xy / G_xy, mu_xy / G_xy, frac(self.G_lt)]
        ])

        T = self.T = np.array([
            [c ** 2, s ** 2, -2 * c * s],
            [s ** 2, c ** 2, 2 * c * s],
            [c * s, -c * s, c ** 2 - s ** 2]
        ])

        self.raideur_matrix_on_coordinate_L_T = np.array([
            [hat_E_l, nu_tl * hat_E_l, 0],
            [hat_E_t * nu_lt, hat_E_t, 0],
            [0, 0, self.G_lt]
        ])

        self.raideur_matrix_on_coordinate_X_Y = np.dot(np.dot(T, self.raideur_matrix_on_coordinate_L_T), T.T)  # np.dot 才是矩阵乘法


class Laminate:
    def __init__(self, layer_infos: List[LayerInfo]):

        self.layers: List[LayerOnCoordinateXY] = [LayerOnCoordinateXY(layer_info.E_l, layer_info.E_t, layer_info.nu_lt, layer_info.G_lt,
                                                                      # 角度制 转 弧度制
                                                                      layer_info.theta / 180 * pi) for layer_info in layer_infos]

        thickness_list = self.thickness_list = [layer_info.thickness for layer_info in layer_infos]
        total_thickness = self.total_thickness = sum(thickness_list)

        self.A = np.zeros((3, 3))
        self.B = np.zeros((3, 3))
        self.C = np.zeros((3, 3))
        for layer_index, layer in enumerate(self.layers):
            Z_k = self.get_Z_k(layer_index + 1)
            Z_k_minus_1 = self.get_Z_k(layer_index)
            self.A += thickness_list[layer_index] * layer.raideur_matrix_on_coordinate_X_Y
            self.B += (Z_k ** 2 - Z_k_minus_1 ** 2) / 2 * layer.raideur_matrix_on_coordinate_X_Y
            self.C += (Z_k ** 3 - Z_k_minus_1 ** 3) / 3 * layer.raideur_matrix_on_coordinate_X_Y

        hat_E_x = (self.A_row_col(1, 1) * self.A_row_col(2, 2) - self.A_row_col(1, 2) ** 2) / (self.A_row_col(2, 2) * total_thickness)
        hat_E_y = (self.A_row_col(1, 1) * self.A_row_col(2, 2) - self.A_row_col(1, 2) ** 2) / (self.A_row_col(1, 1) * total_thickness)
        hat_nu_xy = self.A_row_col(2, 1) / self.A_row_col(2, 2)
        hat_nu_yx = self.A_row_col(2, 1) / self.A_row_col(1, 1)
        hat_G_xy = self.A_row_col(3, 3) / total_thickness
        self.modules_apparents_matrix = np.array([
            [frac(hat_E_x), -hat_nu_yx / hat_E_y, 0],
            [-hat_nu_xy / hat_E_x, frac(hat_E_y), 0],
            [0, 0, frac(hat_G_xy)]
        ])

    def get_Z_k(self, k: int):
        """
        :param k:  第k层板，从1开始计数
        :return: Z_k
        """
        return sum(self.thickness_list[:k]) - self.total_thickness / 2

    def A_row_col(self, row, col):
        return self.A[row - 1][col - 1]

    def print(self):
        print("Laminate:")
        pprint(self.__dict__)
        for index, layer in enumerate(self.layers):
            print(f"\n\n\n-----layer{index + 1}:")
            pprint(layer.__dict__)

    def transform_all_ndarray_attributes_to_list(self):
        transform_all_ndarray_attributes_of_obj_to_list(self)
        for layer in self.layers:
            transform_all_ndarray_attributes_of_obj_to_list(layer)

    def destructive_print(self):
        self.transform_all_ndarray_attributes_to_list()
        self.print()

    def to_json(self):
        self.transform_all_ndarray_attributes_to_list()
        _dict = self.__dict__
        _layers = []
        _dict['layers'] = [layer.__dict__ for layer in _dict.get('layers', [])]
        return json.dumps(_dict)


if __name__ == '__main__':
    DEBUG = True
    if DEBUG:  # TD5
        inputted_E_l = 140e9
        inputted_E_t = 5e9
        inputted_nu_lt = 0.35
        inputted_G_lt = 5e9
        # inputted_theta_list = [45, -45, -45, 45]
        inputted_theta_list = [0, 0, 90, 90, 90, 90, 0, 0]  # TD7
        # inputted_thickness = 1
        inputted_thickness = 2e-3 / 8  # TD7
    else:
        inputted_E_l = input_a_number("请输入E_l(参考值: 140e9)")
        inputted_E_t = input_a_number("请输入E_t(参考值: 5e9)")
        inputted_nu_lt = input_a_number("请输入nu_lt(参考值: 0.35)")
        inputted_G_lt = input_a_number("请输入G_lt(参考值: 4)")
        inputted_layer_amount = input_a_number("请输入层合板的层数(参考值: 4)", is_int=True)
        inputted_theta_list = input_a_number_list("请逐个输入各层板的纤维角度(参考值: 0,45,60,90等角度制数字)", max_length=inputted_layer_amount)
        inputted_thickness = input_a_number("请输入单板层的厚度(0.1)")

    layerInfoList = [LayerInfo(
        E_l=inputted_E_l,
        E_t=inputted_E_t,
        G_lt=inputted_G_lt,
        nu_lt=inputted_nu_lt,
        theta=inputted_theta,
        thickness=inputted_thickness,
    ) for inputted_theta in inputted_theta_list]

    laminate = Laminate(layerInfoList)

    pprint(json.loads(laminate.to_json()))
