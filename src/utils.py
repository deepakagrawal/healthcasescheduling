import pandas as pd
from pathlib import Path
from functools import reduce


def read_file(path: Path):
    if isinstance(path, Path) and path.suffix == ".csv":
        df = pd.read_csv(path)
    elif isinstance(path, list) and path[0].suffix == ".csv":
        df = [pd.read_csv(file) for file in path]
        df = reduce(lambda df1, df2: pd.merge(df1, df2, on='ProviderID', how='outer'), df)
    else:
        raise NotImplementedError(f"`{read_file.__name__}` not implement for type `{path.suffix}`")
    return df


def write_output(df_dict: dict, path: Path):
    with pd.ExcelWriter(path) as writer:
        for key, df in df_dict.items():
            df.to_excel(writer, sheet_name=key, float_format='%.2f')
