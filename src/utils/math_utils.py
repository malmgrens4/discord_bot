def get_percentage(percentage: str, amount: int):
    percentage = int(''.join([i for i in percentage if i.isdigit()]))
    if 0 < percentage <= 100:
        amount = int((percentage * .01 * amount))
        return amount