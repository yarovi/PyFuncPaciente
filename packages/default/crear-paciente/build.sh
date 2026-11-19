#!/bin/bash
set -e

virtualenv --without-pip virtualenv

python3 -m pip install \
  --platform manylinux2014_x86_64 \
  --python-version 3.13 \
  --implementation cp \
  --abi cp313 \
  --only-binary=:all: \
  --target virtualenv/lib/python3.13/site-packages \
  -r requirements.txt