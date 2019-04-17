import ast
import os
import re

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
        .replace('.sort', '.order_by') \
        .replace('ObjectId(', 'bson.ObjectId(')
    return line


def convert_models_file(old_model_dir, model_dir, manager_dir, model_name):
    embedded_structure = ""
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
        for line in old_model_file:
            if 'class ' in line:
                is_class = True
            if '@property' in line:
                is_property = True
            if 'def ' in line and not is_function:
                is_class = False
                is_function = True
                import_module = f'from ..models import {model_name}\n'
                new_funtion_import += import_module
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
                    line = re.sub(r'"[\s]{0,}: ([a-zA-Z\{\}\[\]: ]+),|"[\s]{0,}: ([a-zA-Z\{\}\[\]: ]+[\]\}rte])',
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
                new_fuction_file += line

        embedded_structure, structure = convert_structure(ast.literal_eval(structure))
        model_file.writelines(embedded_structure)
        model_file.writelines(new_class_model)
        model_file.writelines(structure + '\n')
        model_file.writelines(class_meta)
        model_file.writelines(property + '\n')

        manager_file.writelines(f'{new_funtion_import}\n\n')
        manager_file.writelines(new_fuction_file)


for root, dirs, files in os.walk(old_models_dir):
    with open(f'{models_dir}/__init__.py', 'w') as init_file:
        for filename in files:
            if filename != '__init__.py':
                name = filename.split('.')[0]

                model_name = f'{name}.py'
                manager_name = f'{name.lower()}_manager.py'

                old_model_dir = f'{root}/{filename}'
                model_dir = f'{models_dir}/{model_name}'
                manager_dir = f'{managers_dir}/{manager_name}'

                with open(old_model_dir, "r", encoding='utf-8-sig') as f:
                    p = ast.parse(f.read())

                # get all classes from the given python file.
                classes = [c for c in ast.walk(p) if isinstance(c, ast.ClassDef)]
                for x in classes:
                    init_file.writelines(
                        f'from .{filename.replace(".py", "")} import {x.name}\n')

                convert_models_file(old_model_dir, model_dir, manager_dir, classes[0].name)
