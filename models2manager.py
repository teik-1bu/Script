import ast
import os
import re
import pickle

old_models_dir = "./PlayAPI/restApi/old_models"
models_dir = "./PlayAPI/restApi/models"
managers_dir = "./PlayAPI/restApi/managers"

def convert_value(value="", **kwargs):
    options = ""
    for k, v in kwargs.items():
        if v:
            options += f'{k}={v},'
    value = re.sub(r'^\[(\w+)\]$', 'fields.ListField(\\1)', value)
    value = re.sub(r'\{(([\w\s]+:.*)|)\}', 'fields.DictField()', value)
    value = re.sub('str', f'fields.CharField({options[0:-1]})', value)
    value = re.sub('int', f'fields.IntegerField({options[0:-1]})', value)
    value = re.sub('bool', f'fields.BooleanField({options[0:-1]})', value)
    value = re.sub('ObjectId', f'fields.ObjectIdField({options[0:-1]})', value)
    value = re.sub('datetime', f'fields.DateTimeField({options[0:-1]})', value)
    return value


def convert_title(str):
    return "".join([w.title() for w in str.split('_')])


def convert_class(key, dict):
    class_tempt = f'\tclass {convert_title(key)}:\n'
    for key3, value3 in dict:
        value3 = convert_value(value3)
        class_tempt += f'\t\t{key3} = {value3}\n'


def convert_structure(dict):
    structure = ""
    embedded_structure = ""
    for key1, value1 in dict.items():
        if isinstance(value1, __builtins__.dict):
            class_tempt1 = f'class {convert_title(key1)}(EmbeddedMongoModel):\n'
            for key2, value2 in value1.items():
                if isinstance(value2, __builtins__.dict):
                    class_tempt2 = f'class {convert_title(key2)}(EmbeddedMongoModel):\n'
                    for key3, value3 in value2.items():
                        value3 = convert_value(value3, primary_key=True if key3 == '_id' else None)
                        class_tempt2 += f'\t{key3} = {value3}\n'
                    embedded_structure += class_tempt2 + '\n\n'
                    class_tempt1 += f'\t{key2} = EmbeddedDocumentField({convert_title(key2)})\n'
                else:
                    value2 = convert_value(value2, primary_key=True if key2 == '_id' else None)
                    class_tempt1 += f'\t{key2} = {value2}\n'
            embedded_structure += class_tempt1 + '\n\n'
            structure += f'\t{key1} = EmbeddedDocumentField({convert_title(key1)})\n'
        elif isinstance(value1, __builtins__.list):
            class_tempt1 = f'class {convert_title(key1)}(EmbeddedMongoModel):\n'
            for item in value1:
                for key2, value2 in item.items():
                    value2 = convert_value(value2, primary_key=True if key2 == '_id' else None)
                    class_tempt1 += f'\t{key2} = {value2}\n'
            embedded_structure += class_tempt1 + '\n\n'
            structure += f'\t{key1} = EmbeddedDocumentListField({convert_title(key1)})\n'
        else:
            value1 = convert_value(value1, primary_key=True if key1 == '_id' else None)
            structure += f'\t{key1} = {value1}\n'
    return embedded_structure, structure


def convert_fuction(line=""):
    line = line.replace("mdb.", "") \
        .replace('.find_one', '.objects.{}get'.format("" if 'query = ' in line else "values().")) \
        .replace('.find', '.objects.{}raw'.format("" if 'query = ' in line else "values().")) \
        .replace('.collection.aggregate([', '.objects.aggregate(')\
        .replace('], explain=False)', ', explain=False)')\
        .replace('.sort(', '.order_by(') \
        .replace('ObjectId(', 'bson.ObjectId(') \
        .replace(' ObjectId.', ' bson.ObjectId.')
    return line


def convert_models_file(old_model_dir, model_dir, manager_dir, model_name, methods_dict, utils_func_dict):
    with open(old_model_dir, encoding="utf8") as old_model_file, \
            open(model_dir, 'w') as model_file, \
            open(manager_dir, 'w') as manager_file:
        model_file.writelines("from pymodm import MongoModel, EmbeddedMongoModel, fields, EmbeddedDocumentField"
                              ", EmbeddedDocumentListField\n\n")
        is_class = False
        is_property = False
        is_function = False
        is_structure = False
        is_default_value = False
        class_meta = ""
        structure = ""
        property = ""
        new_class_model = ""
        new_fuction_file = ""
        new_funtion_import = ""
        models = []
        managers = []

        for line in old_model_file:
            if 'class ' in line:
                is_class = True
            if '@property' in line:
                is_property = True
            if 'def ' in line and not is_function:
                is_class = False
                is_function = True
            if is_class and not is_property:
                new_line = line.replace('Document', 'MongoModel')
                if 'use_dot_notation' in line or 'use_schemaless' in line:
                    continue
                if '__collection__' in line:
                    collection_name = re.search('\'(.*)\'', line).group(1)
                    class_meta = f'\n\tclass Meta:\n' \
                        f'\t\tcollection_name = \'{collection_name}\'\n' \
                        f'\t\tignore_unknown_fields = True\n' \
                        f'\t\tfinal = True\n'
                    continue
                if 'structure = {' in line:
                    is_structure = True
                    structure += '{\n'
                    continue
                if 'default_values = {' in line:
                    is_default_value = True,
                    continue
                if is_default_value:
                    continue
                if is_structure:
                    line = line.replace('\'', '"')
                    line = re.sub(r'"[\s]*: ([a-zA-Z\{\}\[\]: ]+),|"[\s]*: ([a-zA-Z\{\}\[\]: ]+[\]\}rte])',
                                  '": "\\1\\2",',
                                  line)
                    structure += line

                    continue
                new_class_model += new_line + '\n'
            if is_property:
                if line is '\n':
                    is_property = False
                else:
                    property += '\t' + line
            if is_function and not is_property:
                line = re.sub(r'^\s{4}([\t]{0,}.*)', '\\1', line)
                line = line.replace('self, ', '')
                line = line.replace('(self)', '()')
                line = line.replace('self.', '')
                line = convert_fuction(line)
                if 'bson.' in line and 'import bson' not in new_funtion_import:
                    import_module = 'import bson\n'
                    new_funtion_import += import_module
                if (' datetime' in line or 'timedelta' in line) and 'from datetime import datetime' not in new_funtion_import:
                    import_module = 'from datetime import datetime, timedelta\n'
                    new_funtion_import += import_module
                if 'current_app.' in line and 'from flask' not in new_funtion_import:
                    import_module = 'from flask import current_app\n'
                    new_funtion_import += import_module
                if ' re.' in line and 'import re' not in new_funtion_import:
                    import_module = 'import re\n'
                    new_funtion_import += import_module
                if '(math' in line and 'import math' not in new_funtion_import:
                    import_module = 'import math\n'
                    new_funtion_import += import_module

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

                    line = re.sub(pattern, f'\\1{model}.\\3', line)

                    models.append(model)
                except AttributeError:
                    pass

                # Check and import utils

                try:
                    pattern = r' (\w+?)\('
                    utils_func = re.search(pattern, line).group(1)
                    if utils_func in utils_func_dict.keys():
                        if 'from PlayAPI import utils' not in new_funtion_import:
                            new_funtion_import += 'from PlayAPI import utils\n'
                        line = re.sub(pattern, f' utils.{utils_func}(', line)
                        utils_func_dict[utils_func] = 1
                except:
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


                new_fuction_file += line

        models = list(set(models))
        import_models = ""
        if models:
            import_models = f'from ..models import {", ".join(models)}\n'
        new_funtion_import += import_models

        managers = list(set(managers))
        import_manager = ""
        if managers:
            import_manager = f'from PlayAPI.restApi.managers import {", ".join(managers)}\n'
        new_funtion_import += import_manager

        embedded_structure, structure = convert_structure(ast.literal_eval(structure))
        model_file.writelines(embedded_structure)
        model_file.writelines(new_class_model)
        model_file.writelines(structure + '\n')
        model_file.writelines(class_meta)
        model_file.writelines(property + '\n')

        manager_file.writelines(f'{new_funtion_import}\n\n')
        manager_file.writelines(new_fuction_file)

def convert_old_models(methods_dict, utils_func_dict):
    for root, dirs, files in os.walk(old_models_dir):
        with open(f'{models_dir}/__init__.py', 'w') as init_file:
            for filename in files:
                if filename != '__init__.py':
                    name = filename.split('.')[0]

                    model_name = f'{name}.py'

                    old_model_dir = f'{root}/{filename}'
                    model_dir = f'{models_dir}/{model_name}'

                    with open(old_model_dir, "r", encoding='utf-8-sig') as f:
                        p = ast.parse(f.read())

                    # get all classes from the given python file.
                    classes = [c for c in ast.walk(p) if isinstance(c, ast.ClassDef)]
                    for x in classes:
                        init_file.writelines(
                            f'from .{filename.replace(".py", "")} import {x.name}\n')

                    manager_name = f'{classes[0].name.lower()}_manager.py'
                    manager_dir = f'{managers_dir}/{manager_name}'
                    convert_models_file(old_model_dir, model_dir, manager_dir, classes[0].name, methods_dict, utils_func_dict)


def get_list_func_utils():
    utils_dir = "./PlayAPI/utils.py"
    filename = './Scripts/utils_list.txt'
    try:
        with open(filename, 'rb') as file:
            return pickle.load(file)
    except:
        with open(utils_dir, encoding='utf-8-sig') as utils_file:
            point = ast.parse(utils_file.read())
        funcs_name = [func.name for func in ast.walk(point) if isinstance(func, ast.FunctionDef)]
        with open(filename, 'wb') as file:
            pickle.dump(funcs_name, file)

        return funcs_name


def get_list_func_manager():
    filename = './Scripts/methods_dict.txt'
    try:
        with open(filename, 'rb') as file:
            return pickle.load(file)
    except:
        methods_dict = {}
        for root, dirs, files in os.walk(old_models_dir):
            for file_name in files:
                old_model_dir = f'{root}/{file_name}'
                with open(old_model_dir, "r", encoding='utf-8-sig') as f:
                    node = ast.parse(f.read())
                classes = [n for n in node.body if isinstance(n, ast.ClassDef)]

                for class_ in classes:
                    methods = [n for n in class_.body if isinstance(n, ast.FunctionDef)]
                    for method in methods:
                        methods_dict[f'{class_.name}.{method.name}'] = f'{class_.name.lower()}_manager.{method.name}'
        with open(filename, 'wb') as file:
            pickle.dump(methods_dict, file)

        return methods_dict


if __name__ == "__main__":
    utils_func_dict = {}
    methods_dict = get_list_func_manager()
    utils_func_list = get_list_func_utils()
    for func in utils_func_list:
        utils_func_dict[func] = 0
    convert_old_models(methods_dict, utils_func_dict)

    # for key, value in utils_func_dict.items():
    #     if value == 0:
    #         print(key)

