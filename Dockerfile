FROM python:3.8

WORKDIR /usr/src/hector

COPY requirements ./

RUN pip install --no-cache-dir -r requirements

COPY . .

CMD ["python3", "./hector.py"]
