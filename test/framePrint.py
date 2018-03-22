#!/usr/bin/env python3
# bad Apple text output demo
# author: Sonny Yang

import time
import sys
import os

default_file = 'bad_apple.txt'


def print_line(times, file):
    with open(file) as f:
        frame = ''
        for index, line in enumerate(f, 1):
            frame += line
            if index % 80 == 0:
                print(frame, flush=True)
                frame = ''
                time.sleep(times)


def main():
    movie_file = default_file

    if len(sys.argv) == 2:
        movie_file = sys.argv[1]

    if os.path.isfile(movie_file):
        print_line(0.033, movie_file)
    else:
        raise FileExistsError('parameter {} not is file!'.format(movie_file))


if __name__ == '__main__':
    main()
