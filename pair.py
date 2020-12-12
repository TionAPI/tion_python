#!/usr/bin/env python3
import sys
from tion_btle.s3 import S3 as s3device

s3 = s3device(sys.argv[1])
s3.pair()
