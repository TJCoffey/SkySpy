FROM python:3.7-alpine

LABEL maintainer="tjcoffey" \
      description="SkySpy"

COPY requirements.txt /
RUN pip install -r /requirements.txt

COPY . /app
WORKDIR /app

CMD ["python3", "-u", "request.py"]
