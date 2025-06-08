import binascii
import struct
import base64
import json
import os
from Crypto.Cipher import AES
import requests
import eyed3
import warnings
import time


# 下载网页图片
def download_pic(url, save_fn):
    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/100.0.4896.127 Safari/537.36 "
    }
    
    for i in range(3):
        try:
            response = requests.get(url=url, headers=headers)
            break
        except Exception:
            print("图片下载异常，等待重试。。。")
            time.sleep(5)
            continue
    else:
        assert 0, "图片下载失败"

    with open(save_fn, 'wb') as f:
        f.write(response.content)


# 给mp3文件添加封面
def add_cover_2_mp3(mp3_fp, pic_fp):
    audio_file = eyed3.load(mp3_fp)
    if audio_file.tag is None:
        audio_file.initTag()
    audio_file.tag.images.set(3, open(pic_fp, 'rb').read(), 'image/jpeg')
    audio_file.tag.save()


def dump(input_fp, output_fp):
    #十六进制转字符串
    core_key = binascii.a2b_hex("687A4852416D736F356B496E62617857")
    meta_key = binascii.a2b_hex("2331346C6A6B5F215C5D2630553C2728")
    unpad = lambda s: s[0:-(s[-1] if type(s[-1]) == int else ord(s[-1]))]
    f = open(input_fp, 'rb')
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
    m = open(output_fp, 'wb')
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
        # todo: 是否可能有其他格式
        warnings.warn(f"图片不是jpg格式，不支持添加封面: {cover_url}")
    else:
        tmp_jpg_fn = os.path.join(os.path.dirname(output_fp), f".temp_{os.path.basename(output_fp)}.jpg")
        download_pic(cover_url, tmp_jpg_fn)
        add_cover_2_mp3(output_fp, tmp_jpg_fn)
        os.remove(tmp_jpg_fn)
    return file_name


if __name__ == '__main__':
    # 将目录中的ncm文件转成mp3(多线程版本)
    import os
    from tqdm import tqdm
    import psutil
    from concurrent.futures import ThreadPoolExecutor, wait
    import argparse
    parser = argparse.ArgumentParser(description="nothing")
    parser.add_argument('-p', action='store')
    args = parser.parse_args()
    ncm_path = args.p

    assert ncm_path, "请输入正确的路径"

    MAX_CPU_PERCENT = 80  # 最大CPU占用率
    output_path = os.path.join(ncm_path, "output") # 默认输出到原路径的output目录下
    os.makedirs(output_path, exist_ok=True)

    #@ multithread
    def dump_ncm_to_mp3(input_fp, output_fp):
        if input_fp[-4:].lower() != ".ncm":
            return  # 跳过非ncm文件
        
        if os.path.exists(output_fp):
            return  # 跳过已转换文件
        
        for i in range(5):
            try:
                # 动态调整线程数
                while psutil.cpu_percent(1) > MAX_CPU_PERCENT:
                    pass  # 等待CPU占用下降
                dump(input_fp, output_fp)
                # print(input_fp, " 转换成功")
                return True
            except Exception as e:
                time.sleep(3)
        else:
            print(f"转换失败，文件：{input_fp}")
            return False


    def run():
        cpu_count = os.cpu_count()
        max_workers = max(1, int(cpu_count * 0.8))  # 最大进程数量，这里使用80%的cpu核数

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    dump_ncm_to_mp3, 
                    os.path.join(ncm_path, os.path.basename(file)), 
                    os.path.join(output_path, os.path.basename(file)[:-3]+"mp3"),
                ) 
                for file in os.listdir(ncm_path)
            ]
            
            # 进度条显示
            with tqdm(total=len(futures), desc="Converting") as pbar:
                for future in futures:
                    future.add_done_callback(lambda _: pbar.update(1))
                wait(futures)

    run()

