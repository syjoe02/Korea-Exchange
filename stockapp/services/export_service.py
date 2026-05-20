from io import BytesIO

import pandas as pd


def build_stock_excel(stock_data: list[dict]) -> BytesIO:
    df = pd.DataFrame(stock_data)[["Date", "Close"]]
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output
