def format_number(value):
    return str('{:,}'.format(value))

def discord_display_at_username(user_id):
    return '<@!%s>'%user_id

def create_display_table(headers, rows, col_length=15):
    header_display=''
    underline = ''
    bottom = ''
    side_bar = '|'
    for header in headers:
        header_display+= (side_bar + str(header)).ljust(col_length)
        underline+= ''.ljust(col_length, '=')
        bottom+=''.ljust(col_length, '=')

    header_display += '\n'
    underline += '\n'
    bottom += '\n'

    rows_display=''
    for row in rows:
        row_display=''
        for value in row:
            row_display+= (side_bar + str(value)).ljust(col_length)
        row_display+= side_bar + '\n'
        rows_display+=row_display

    return header_display + underline + rows_display + bottom