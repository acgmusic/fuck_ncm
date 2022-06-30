import binascii
import struct
import base64
import json
import os
from Crypto.Cipher import AES
import requests
import eyed3
import warnings


# 下载网页图片
def download_pic(url, save_fn):
    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/100.0.4896.127 Safari/537.36 "
    }
    response = requests.get(url=url, headers=headers)
    with open(save_fn, 'wb') as f:
        f.write(response.content)


# 给mp3文件添加封面
def add_cover_2_mp3(mp3_fp, pic_fp):
    audio_file = eyed3.load(mp3_fp)
    if audio_file.tag is None:
        audio_file.initTag()
    audio_file.tag.images.set(3, open(pic_fp, 'rb').read(), 'image/jpeg')
    audio_file.tag.save()


def dump(file_path):
    #十六进制转字符串
    core_key = binascii.a2b_hex("687A4852416D736F356B496E62617857")
    meta_key = binascii.a2b_hex("2331346C6A6B5F215C5D2630553C2728")
    unpad = lambda s: s[0:-(s[-1] if type(s[-1]) == int else ord(s[-1]))]
    f = open(file_path, 'rb')
    header = f.read(8)
    #字符串转十六进制
    assert binascii.b2a_hex(header) == b'4354454e4644414d'
    f.seek(2,1)
    key_length = f.read(4)
    key_length = struct.unpack('<I', bytes(key_length))[0]
    key_data = f.read(key_length)
    key_data_array = bytearray(key_data)
    for i in range(0, len(key_data_array)):
        key_data_array[i] ^= 0x64
    key_data = bytes(key_data_array)
    cryptor = AES.new(core_key, AES.MODE_ECB)
    key_data = unpad(cryptor.decrypt(key_data))[17:]
    key_length = len(key_data)
    key_data = bytearray(key_data)
    key_box = bytearray(range(256))
    c = 0
    last_byte = 0
    key_offset = 0
    for i in range(256):
        swap = key_box[i]
        c = (swap + last_byte + key_data[key_offset]) & 0xff
        key_offset += 1
        if key_offset >= key_length:
            key_offset = 0
        key_box[i] = key_box[c]
        key_box[c] = swap
        last_byte = c
    meta_length = f.read(4)
    meta_length = struct.unpack('<I', bytes(meta_length))[0]
    meta_data = f.read(meta_length)
    meta_data_array = bytearray(meta_data)
    for i in range(0, len(meta_data_array)):
        meta_data_array[i] ^= 0x63
    meta_data = bytes(meta_data_array)
    meta_data = base64.b64decode(meta_data[22:])
    cryptor = AES.new(meta_key, AES.MODE_ECB)
    meta_data = unpad(cryptor.decrypt(meta_data)).decode('utf-8')[6:]
    meta_data = json.loads(meta_data)
    # 专辑封面地址
    cover_url = meta_data['albumPic']
    crc32 = f.read(4)
    crc32 = struct.unpack('<I', bytes(crc32))[0]
    f.seek(5, 1)
    image_size = f.read(4)
    image_size = struct.unpack('<I', bytes(image_size))[0]
    image_data = f.read(image_size)
    file_name = f.name.split("/")[-1].split(".ncm")[0] + '.' + meta_data['format']
    m = open(os.path.join(os.path.split(file_path)[0], file_name), 'wb')
    chunk = bytearray()
    while True:
        chunk = bytearray(f.read(0x8000))
        chunk_length = len(chunk)
        if not chunk:
            break
        for i in range(1, chunk_length+1):
            j = i & 0xff
            chunk[i-1] ^= key_box[(key_box[j] + key_box[(key_box[j] + j) & 0xff]) & 0xff]
        m.write(chunk)
    m.close()
    f.close()
    # 添加封面
    if cover_url[-3:] != "jpg":
        warnings.warn(f"图片不是jpg格式，不支持添加封面: {cover_url}")
    else:
        download_pic(cover_url, "./temp.jpg")
        add_cover_2_mp3(file_name, "./temp.jpg")
        os.remove("./temp.jpg")
    return file_name


if __name__ == '__main__':
    # 将目录中的ncm文件转成mp3
    def crack_ncm_file(path):
        for file in os.listdir(path):
            file_path = os.path.join(path, file)
            if file[-3:] == 'ncm':
                dump(file_path)
                os.remove(file_path)
                print(file_path, " 转换成功")
    import argparse
    parser = argparse.ArgumentParser(description="nothing")
    parser.add_argument('-p', action='store')
    args = parser.parse_args()
    crack_ncm_file(args.p)

    # path = r"D:\chord_analyzer\songs\田中秀和"
    #
    # crack_ncm_file(path)
