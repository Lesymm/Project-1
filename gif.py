def load_file(file_name: str) -> tuple[bytes, str]:
    """
    Takes the file name of a .gif file and return a data object and a description line. \n
    If the GIF file was found, its entire content should be transferred into data. If the file was not found, return an
    empty bytes() \n
    If the file was opened, info returns the file_name. If the file was not found, info return 'file not found'. \n
    :param file_name: path to the .gif file
    :return: tuple of (data, info)
    """
    # open file for reading using binary mode
    try:
        with open(file_name, "rb") as fh:
            data = fh.read()
        info = file_name
    # if not found return "file not found" and empty bytes()
    except FileNotFoundError:
        data = bytes()
        info = "file not found"
    return data, info


def extract_header(data: bytes) -> str:
    """
    Extract the GIF header from data.\n
    :param data: obtained using load_file()
    :return: header
    """
    # the header is decoded according to ascii
    header = data[0:6].decode("ascii")
    return header


def extract_screen_descriptor(data: bytes) -> tuple[int, int, int, int, int, int, int, int]:
    """
    Extract the screen descriptors from data.\n
    :param data: obtained using load_file()
    :return: width, height, gc_fl, cr, sort_fl, gc_size, bcolour_i, and px_ratio - values returned are as specified in
    the GIF documentation
    """
    # reading multi-byte data using little-endian format
    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    # reading single byte data
    bcolour_i = data[11]
    px_ratio = data[12]

    # converting packed field byte into bits
    packed_field = bin(data[10])[2:]
    # reading packed field bits
    gc_fl = int(packed_field[0])
    cr = int(packed_field[1:4], base=2)
    sort_fl = int(packed_field[4])
    gc_size = int(packed_field[5:8], base=2)
    return width, height, gc_fl, cr, sort_fl, gc_size, bcolour_i, px_ratio


def extract_global_colour_table(data: bytes) -> list[list[int, int, int], ...]:
    """
    Extract the global colour map from data.\n
    :param data: obtained using load_file()
    :return: gc_map - contains the global colour table as a 2-dimensional array with each row representing a different
    colour in the table and each column representing the colour, such as red, green, and blue.
    """
    # get table size from logical screen descriptor and slicing data
    table_size = 3 * 2 ** (extract_screen_descriptor(data)[5] + 1)
    table_bytes = data[13:13 + table_size]

    # create table of rgb values
    gc_map = []
    for c in range(0, len(table_bytes), 3):
        # pull rgb values 3 bytes at a time
        color = [n for n in table_bytes[c:c+3]]
        gc_map.append(color)
    return gc_map


def extract_image_descriptor(data: bytes) -> tuple[int, int, int, int, int, int, int, int, int]:
    """
    Extract the image descriptors from data.\n
    :param data: obtained using load_file()
    :return: left, top, width, height, lc_fl, itl_fl, sort_fl, res, and lc_size - values returned are as specified in
    the GIF documentation.
    """
    # locate image descriptor start byte -> should be the first 2C byte after gc_map
    table_size = 3 * 2 ** (extract_screen_descriptor(data)[5] + 1)
    search_start = 13 + table_size
    start = data.find(b"\x2c", search_start)

    # read two-byte descriptors using little-endian format
    left = int.from_bytes(data[start + 1:start + 3], "little")
    top = int.from_bytes(data[start + 3:start + 5], "little")
    width = int.from_bytes(data[start + 5:start + 7], "little")
    height = int.from_bytes(data[start + 7:start + 9], "little")

    # find packed field descriptors
    packed_field = bin(data[start + 9])[2:]
    # if packed field is 0, then all fields are 0
    if packed_field == "0":
        lc_fl = itl_fl = sort_fl = res = lc_size = 0
    # read packed field bits
    else:
        lc_fl = int(packed_field[0])
        itl_fl = int(packed_field[1])
        sort_fl = int(packed_field[2])
        res = int(packed_field[2:4], base=2)
        lc_size = int(packed_field[4:7], base=2)
    return left, top, width, height, lc_fl, itl_fl, sort_fl, res, lc_size


def extract_image(data: bytes) -> list[list[list[int, ...], ...], ...]:
    """
    Extract the image from data.
    :param data: obtained using load_file()
    :return: image - The return should be a 3-dimensional array containing the decompressed GIF image. The first
    dimension should be rows, the second dimension should be columns, and the third dimension should be the colours,
    such as red, green, blue.
    """
    # locate image start -> 10 bytes after start of image descriptor
    table_size = 3 * 2 ** (extract_screen_descriptor(data)[5] + 1)
    search_start = 13 + table_size
    start = data.find(b"\x2c", search_start) + 10
    image_bytes = data[start:]

    # get minimum code size from byte 0 of image data
    min_code_size = image_bytes[0]
    # starting code size is one more than min_code_size
    code_size = min_code_size + 1

    # generate data_stream to read variable length codes -> combine all data from all data sub blocks
    # equivalent to removing the data sub block length bytes
    # looping through data sub blocks and setting default values
    sub_blocks = []
    sub_block_start = 1
    sub_block_length = image_bytes[sub_block_start]
    data_stream = []
    # sub_block_length = 0 marks end of image data
    while sub_block_length != 0:
        sub_block = image_bytes[sub_block_start + 1: sub_block_start + sub_block_length + 1]
        # turn sub block data into series of bits
        string_list = []
        for byte in sub_block:
            long_byte = bin(byte)[2:]
            # force long_byte to be 8-bit
            if len(long_byte) < 8:
                long_byte = (8 - len(bin(byte)[2:])) * "0" + long_byte
            # bytes are added with the least significant bit first
            string_list.append(long_byte[::-1])
        stream = "".join(string_list)
        data_stream.append(stream)

        # getting next sub_block start index and length
        sub_block_start += sub_block_length + 1
        sub_block_length = image_bytes[sub_block_start]
    data_stream = "".join(data_stream)

    # LZW Algorithm main loop works as follows:
    # let current_code be the next code chunk in data_stream
    # if current_code in code_table:
    # A) add current_code color(s) to image_data
    # B) let b be the first color from current_code
    # C) add (previous_code + b) colors to code_table
    # if current_code not in code_table:
    # A) let b be the first color from previous_code
    # B) add (previous_code + b) colors to image_data
    # C) add (previous_code + b) colors to code_table
    # for first "color" code -> append current_code color to image_data, then start main loop
    # keep count of codes read when looping through data stream
    start_b = 0
    count = 0
    gc_map = extract_global_colour_table(data)  # fresh color table
    cc_index = len(gc_map)  # clear code index
    image_data = []
    while True:
        # chunk of bits is reversed after slicing to read correctly
        reversed_order = data_stream[start_b:start_b + code_size]
        current_code = int(reversed_order[::-1], base=2)
        start_b += code_size

        # CC - initialize code table color map
        if current_code == cc_index:
            # get global color table
            code_table = [[c] for c in gc_map]
            # add special lzw codes - Clear Code and End Of Information
            code_table.extend(["CC", "EOI"])
            first = True  # will treat next code as first "color" code
            # reset code_size and count
            count = 0
            code_size = min_code_size + 1
        # EOI - break out of loop
        elif current_code == cc_index + 1:
            break
        # code is in code table
        elif current_code < len(code_table):
            # add current_code color(s) to image data
            current_color = code_table[current_code]
            image_data.extend(current_color)
            # if first code do not change code table
            if first:
                first = False
            # else create new code table entry
            else:
                b = current_color[0]
                new = code_table[previous_code] + [b]
                code_table.append(new)
        # code is not in code table
        else:
            # update image_data and code_table
            b = code_table[previous_code][0]
            new = code_table[previous_code] + [b]
            image_data.extend(new)
            code_table.append(new)

        # saving previous code and keeping count
        count += 1
        previous_code = current_code
        # adjusting code size
        if count == 2 ** (code_size - 1):
            count = 0
            code_size += 1

    # get image width and reshape image
    width = extract_image_descriptor(data)[2]
    image = []
    row = []
    for index, color in enumerate(image_data, start=1):
        row.append(color)
        # create new row after width is satisfied
        if index % width == 0:
            image.append(row)
            row = []
    return image
