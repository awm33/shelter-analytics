import time
import tempfile
import os
import re
import shutil
from datetime import datetime, timedelta

import click
from selenium import webdriver
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
import petl

from models import BaseModel, Animal

@click.group()
def main():
    pass

def wait_for_download_and_move(tmp_dir, output_directory, download_timeout):
    for i in range(0, download_timeout):
        files = list(os.listdir(tmp_dir))
        if len(files) > 0 and re.match(r'.+\.xls$', files[0]) != None:
            filename = files[0]
            shutil.move(
                os.path.join(tmp_dir, filename),
                os.path.join(output_directory, filename))
            break
        else:
            time.sleep(1)

def animal_intake_extended(driver, tmp_dir, output_directory, download_timeout):
    intake_reports = driver.find_element_by_link_text('Intake')
    intake_reports.click()
    intake_report_extended = driver.find_element_by_link_text('Animal: Intake Extended')
    intake_report_extended.click()

    start_date = (datetime.now() - timedelta(days=730)).strftime('%-m/%-d/%Y %-I:%-M %p')
    start_date_input = driver.find_element_by_id('Date_IntakeStart')
    start_date_input.clear()
    start_date_input.send_keys(start_date)
    time.sleep(1)
    submit = driver.find_element_by_id('validate')
    submit.click()

def animal_intake_with_results_extended(driver, tmp_dir, output_directory, download_timeout):
    intake_reports = driver.find_element_by_link_text('Intake')
    intake_reports.click()
    intake_report_extended = driver.find_element_by_link_text('Animal: Intake with Results Extended')
    intake_report_extended.click()

    start_date = (datetime.now() - timedelta(days=730)).strftime('%-m/%-d/%Y %-I:%-M %p')
    start_date_input = driver.find_element_by_id('IntakeDateFrom')
    start_date_input.clear()
    start_date_input.send_keys(start_date)
    time.sleep(1)

    driver.execute_script("document.getElementById('ActiveAnimals').value = '1';")
    time.sleep(1)

    submit = driver.find_element_by_id('validate')
    submit.click()

@main.command()
@click.argument('output_directory', type=click.Path(exists=True))
@click.option('--download-timeout', type=int, default=60)
@click.option('--shelter-id')
@click.option('--username')
@click.option('--password')
def download_reports(output_directory, download_timeout, shelter_id, username, password):
    shelter_id = shelter_id or os.getenv('PETPOINT_SHELTER_ID')
    username = username or os.getenv('PETPOINT_USERNAME')
    password = password or os.getenv('PETPOINT_PASSWORD')

    with tempfile.TemporaryDirectory() as tmp_dir:
        chromeOptions = webdriver.ChromeOptions()
        prefs = {"download.default_directory" : tmp_dir}
        chromeOptions.add_experimental_option("prefs", prefs)

        driver = webdriver.Chrome(chrome_options=chromeOptions)
        driver.implicitly_wait(10) # seconds

        # login
        driver.get("https://sms.petpoint.com/sms3/forms/signinout.aspx")
        shelter_id_input = driver.find_element_by_id('cphSearchArea_txtShelterPetFinderId')
        shelter_id_input.send_keys(shelter_id)
        shelter_username = driver.find_element_by_id('cphSearchArea_txtUserName')
        shelter_username.send_keys(username)
        shelter_password = driver.find_element_by_id('cphSearchArea_txtPassword')
        shelter_password.send_keys(password)
        submit = driver.find_element_by_id('cphSearchArea_btn_SignIn')
        submit.click()

        # go to reporting website
        reports_menu = driver.find_element_by_link_text('Reports')
        reports_menu.click()
        reports_site_link = driver.find_element_by_link_text('Report Website')
        reports_site_link.click()
        driver.switch_to_window(driver.window_handles[-1])

        animal_intake_extended(driver, tmp_dir, output_directory, download_timeout)
        wait_for_download_and_move(tmp_dir, output_directory, download_timeout)

        driver.back()

        animal_intake_with_results_extended(driver, tmp_dir, output_directory, download_timeout)
        wait_for_download_and_move(tmp_dir, output_directory, download_timeout)

        driver.quit()

def to_bool(value):
    if value.strip() == 'Yes' or value.strip() == 'Y':
        return True
    return False

def normalize_string(value):
    value = value.strip()
    if value == '':
        value = None
    return value

def process_animal_extended(shelter_id, session, input_directory):
    table = petl.fromxls(
                os.path.join(input_directory, 'AnimalIntakeExtended.xls'),
                sheet='AnimalIntakeExtended')

    ## Because an animal can appear in the intake report more than once,
    ## we must sort the table in order to upsert the latest value
    table_sorted = petl.sort(table, key='Intake Date/Time')

    for row in petl.dicts(table_sorted):
        id = row['Animal ID']

        set_values = {
            'arn': normalize_string(row['ARN']),
            'name': normalize_string(row['Animal Name']),
            'species': normalize_string(row['Species']),
            'primary_breed': normalize_string(row['Primary Breed']),
            'secondary_bred': normalize_string(row['Secondary Breed']),
            'gender': normalize_string(row['Gender']),
            'pre_altered': to_bool(row['Pre Altered']),
            'altered': to_bool(row['Altered']),
            'primary_color': normalize_string(row['Primary Colour']),
            'secondary_color': normalize_string(row['Secondary Colour']),
            'third_color': normalize_string(row['Third Colour']),
            'color_pattern': normalize_string(row['Colour Pattern']),
            'second_color_pattern': normalize_string(row['Second Colour Pattern']),
            'size': normalize_string(row['Size'])
        }

        insert_stmt = insert(Animal)\
            .values(
                id=id,
                shelter_id=shelter_id, ## TODO: add to index for constraint? make composite pk?
                **set_values)\
            .on_conflict_do_update(
                constraint='animals_pkey',
                set_={
                    'shelter_id': shelter_id,
                    **set_values,
                    'updated_at': func.now()
                })

        session.execute(insert_stmt)
        session.commit()

@main.command()
@click.argument('input_directory', type=click.Path(exists=True))
@click.option('--shelter-id')
@click.option('--connection-string')
def sync_reports(input_directory, shelter_id, connection_string):
    shelter_id = shelter_id or os.getenv('PETPOINT_SHELTER_ID')
    connection_string = connection_string or os.getenv('CONNECTION_STRING')

    engine = create_engine(connection_string)
    Session = sessionmaker(bind=engine)
    
    session = Session()

    process_animal_extended(shelter_id, session, input_directory)

    session.close()

@main.command()
@click.option('--connection-string')
def init_db(connection_string):
    connection_string = connection_string or os.getenv('CONNECTION_STRING')

    engine = create_engine(connection_string)

    BaseModel.metadata.create_all(engine)

if __name__ == '__main__':
    main()
