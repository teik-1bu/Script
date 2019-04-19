import os
import pickle
import re

old_api_dir = "./PlayAPI/old_restApi_ver6"
new_api_dir = "./PlayAPI/restApi_ver6"


def convert_import_block(str):
    str = str.replace('mdb, ', '') \
        .replace(', mdb', '') \
        .replace('from ...extensions import mdb', '') \
        .replace('from ...app import current_app', 'from flask import current_app')
    return str


def convert_body(line):
    new_line = line.replace("mdb.", "") \
        .replace('.find_one', '.objects.{}get'.format("" if 'query = ' in line else "values().")) \
        .replace('.find', '.objects.{}raw'.format("" if 'query = ' in line else "values().")) \
        .replace('.raw()', '.all()') \
        .replace('.collection.aggregate([', '.objects.aggregate(') \
        .replace('], explain=False)', ', explain=False)') \
        .replace('.sort(', '.order_by(') \
        .replace('ObjectId(', 'bson.ObjectId(') \
        .replace(' ObjectId.', ' bson.ObjectId.')
    return new_line


def convert_old2new(old_dir, new_dir, methods_dict):
    for root, dir, files in os.walk(old_dir):
        for file in files:
            new_root = root.replace('old_', '')
            old_file = f'{root}/{file}'
            new_file = f'{new_root}/{file}'

            if not os.path.exists(new_root):
                os.makedirs(new_root)

            begin_line = ""
            import_block = ""
            body_block = ""
            models = []
            managers = []
            begin_fine_one = False
            find_one_func_block = ""
            var_tempt = ""
            with open(old_file, 'r') as old_f, open(new_file, 'w') as new_f:
                for line in old_f:
                    if 'coding:' in line:
                        begin_line = line
                        continue
                    if 'setdefaultencoding' in line:
                        continue
                    if line.startswith('import') or line.startswith('from'):
                        import_block += line
                        while re.match(r'.*\\$', line):
                            line = next(old_f, '')
                            import_block += line
                    else:
                        line = convert_body(line)

                        # check and import model
                        try:
                            pattern = r'([ (])(\w+?)\.(objects\.|update\()'
                            model = re.search(pattern, line).group(2)

                            if model == 'videos_ver2':
                                model = 'Videos_ver2'
                            elif model == 'structure':
                                model = 'Structure'
                            elif model == 'event_feeder':
                                model = 'EventFeeder'
                            elif model == 'hot_movies':
                                model = 'HotMovies'
                            elif model == 'notification':
                                model = 'Notification'
                            elif model == 'people':
                                model = 'People'
                            elif model == 'mobile_ads':
                                model = 'MobileAds'

                            line = re.sub(pattern, f'\\1{model}.\\3', line)

                            models.append(model)
                        except AttributeError:
                            pass

                            # Check import method
                            pattern = r'(.+?) (\w+?)\.((get\_|find\_|update\_|count\_|is\_|new\_|like\_|add\_|sort\_)[^\(]+)(\(.+)'
                            try:
                                model_class = re.search(pattern, line).group(2)
                                func_name = re.search(pattern, line).group(3)
                                string = f'{model_class}.{func_name}'
                                string_converted = methods_dict[string]
                                line = re.sub(pattern, f'\\1 {string_converted}\\5', line)
                                managers.append(string_converted.split('.')[0])
                            except Exception as e:
                                pass

                        if 'values().get(' in line:
                            begin_fine_one = True
                            var_tempt = re.search('(\w+) (.+?)', line).group(1)
                            if 'return' not in var_tempt:
                                var_tempt += ' ='
                            if 'import sys' not in import_block:
                                import_module = 'import sys\n'
                                import_block += import_module
                            if 'import traceback' not in import_block:
                                import_module = 'import traceback\n'
                                import_block += import_module
                            find_one_func_block += '        try:\n'

                        if begin_fine_one:
                            find_one_func_block += f'            {line}'
                            if '})' in line or 'filter)' in line:
                                begin_fine_one = False
                                except_block = '        except Exception:\n' \
                                    f'            traceback.print_exc(limit=2, file=sys.stdout)\n' \
                                    f'            {var_tempt} None\n'
                                find_one_func_block += except_block
                                body_block += find_one_func_block
                                find_one_func_block = ""
                        else:
                            body_block += line

                if 'import bson' not in import_block:
                    import_module = 'import bson\n'
                    import_block += import_module

                models = list(set(models))
                if models:
                    import_models = f'from PlayAPI.restApi.models import {", ".join(models)}\n'
                    import_block += import_models

                managers = list(set(managers))
                if managers:
                    import_manager = f'from PlayAPI.restApi.managers import {", ".join(managers)}\n'
                    import_block += import_manager

                import_block = convert_import_block(import_block)
                new_f.writelines(begin_line)
                new_f.writelines(import_block)
                new_f.writelines(body_block)


if __name__ == '__main__':
    methods_dict = {}
    filename = './Scripts/methods_dict.txt'
    with open(filename, 'rb') as file:
        methods_dict = pickle.load(file)
    convert_old2new(old_api_dir, new_api_dir, methods_dict)
