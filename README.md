
# Spry Backend

## Environment Variables

Before running the project, make sure to create a `.env` file based on the `.env.example` file provided. 

## Pre-commit

We use [pre-commit](https://pre-commit.com/#installation).

1. Install **pre-commit**:
```bash
  pip install pre-commit
```
2. Install the git hooks:
```bash
  pre-commit install
```
## Start 

1. First you need to install docker. 
2. After that, you need to build docker
```bash
  make build
```
3. After that, you need to run
```bash
  make run
```
## View Available Commands

To see a list of available commands and their descriptions, run:
```bash
  make help
```