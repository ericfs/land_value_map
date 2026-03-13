# CT Land Value Map

Use this repo to compute and map parcel value per acre for property in CT using data from https://data.ct.gov/Local-Government/2024-Connecticut-Parcel-and-CAMA-Data/pqrn-qghw/about_data

Used to generate https://map.strongerhaven.org

## Prereqs

- Get an API key from https://cloud.maptiler.com/account/keys/

## Build and test

Copy the example config files and fill in your API keys:

```sh
cp ansible/example.config.yml ansible/config.yml
cp ansible/example.dev.yml ansible/dev.yml      # for local dev
cp ansible/example.prod.yml ansible/prod.yml    # for production
```

Then build:

```sh
git clone https://github.com/ericfs/land_value_map.git
cd land_value_map
./scripts/build.sh          # defaults to dev
./scripts/build.sh prod     # production build
```

Visit http://localhost:8080