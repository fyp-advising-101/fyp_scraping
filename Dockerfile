# Use Python 3.10 as the base image
FROM python:3.10-slim

RUN apt-get update --fix-missing && \
    apt-get install -y --fix-missing build-essential 

    
COPY ./requirements.txt /app/requirements.txt

# Set the working directory
WORKDIR /app

# Install required Python packages
RUN pip install -r requirements.txt

# Copy the current directory contents into the container
COPY . .

# Expose port 5001
EXPOSE 3001

ENV DATABASE_URL=mysql+pymysql://user:hello123@docker.for.mac.host.internal:3306/fyp_db


# Command to run the application
CMD ["python3", "app.py"]

