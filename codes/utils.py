import os
import requests
import datetime
import tabula
import pandas as pd
pd.options.mode.chained_assignment = None
import geopandas as gpd

import matplotlib.pyplot as plt
import seaborn as sns

def download_data(start_dt, end_dt, directory='output'):
    """
    Download COVID data of barangays in Quezon City.

    Args:
        start_dt (tuple): contains start date to extract data, example (2021, 1, 1) # Jan 1, 2021
        end_dt (tuple): contains end date to extract data, example (2021, 1, 5) # Jan 5, 2021
        directory (str): filepath to save downloaded data

    Returns:
        None
    """


    os.makedirs(directory, exist_ok=True)

    start_date = datetime.date(start_dt[0], start_dt[1], start_dt[2])
    end_date = datetime.date(end_dt[0], end_dt[1], end_dt[2])

    delta = datetime.timedelta(days=1)

    while start_date <= end_date:

        year = start_date.strftime("%Y")
        month = start_date.strftime("%m")

        filename = f'{start_date.strftime("%B-%d-%Y")}-Cases.pdf'

        url = f'https://quezoncity.gov.ph/wp-content/uploads/2021/{month}/{filename}'
        response = requests.get(url)

        responseString = str(response)
        if responseString == '<Response [200]>':
            with open(f'{directory}/{filename}', 'wb') as fd:
                for chunk in response.iter_content(chunk_size=100):
                    fd.write(chunk)
        else:
            print(f'No data extracted on {start_date.strftime("%B %d, %Y")}')

        start_date += delta


def extract_table(file):
    """
    Extracts table from COVID data of Quezon City.

    Args:
        file (str): filepath of pdf

    Returns:
        covid_data (dataframe): table containing the extracted data
    """

    results = []

    tables = tabula.read_pdf(file, pages = "all", multiple_tables = True)
    for table in tables:
        df = table.copy()
        df.columns = df.iloc[0, :].values
        results.append(df.iloc[1:-1,:])

    covid_data = pd.concat(results)

    return covid_data


def preprocess(covid_data, shapefiles_location):
    """
    Preprocesses COVID data and add geometry data to each barangay.

    Args:
        covid_data (dataframe): table containing the extracted data
        shp_file_location (str): location of shapefiles

    Returns:
        df (dataframe): table containing the preprocessed data with geometry information

    """

    rep = {'Bagong Pag‐Asa': 'Bagong Pag-Asa', 'Don_a Imelda': 'Doña Imelda',
           'Don_a Josefa': 'Doña Josefa', 'Duyan‐Duyan': 'Duyan-Duyan',
           'Pag‐Ibig Sa Nayon': 'Pag-Ibig Sa Nayon', 'Pasong Putik': 'Pasong Putik Proper',
          'Phil‐Am': 'Phil-Am', 'Quirino 2‐A': 'Quirino 2-A', 'Quirino 2‐B':'Quirino 2-B',
           'Quirino 2‐C' :'Quirino 2-C', 'Quirino 3‐A': 'Quirino 3-A', 'San Isidro Galas': 'San Isidro',
          'San Martin De Porres':'San Martin de Porres', 'Santo Nin_o': 'Santo Niño', 'Siena': 'Sienna'}

    covid_data = covid_data.replace({'Barangay': rep})

    for feature in ['Active', 'Died', 'Recovered', 'Total']:
        covid_data[feature] = pd.to_numeric(covid_data[feature])
        covid_data[feature] = covid_data[feature].fillna(0)

    map_df = gpd.read_file(shapefiles_location)
    qc_df = map_df[(map_df['REGION'] == 'Metropolitan Manila') & (map_df['NAME_2'] == 'Quezon City')]
    qc_df['coords'] = qc_df['geometry'].apply(lambda x: x.representative_point().coords[:])
    qc_df['coords'] = [coords[0] for coords in qc_df['coords']]
    qc_df['Barangay'] = qc_df['NAME_3'].values
    qc_df = qc_df.replace({'Barangay': {'Constitution Hills': 'Commonwealth'}})

    df = qc_df.merge(covid_data, how='left', on ='Barangay')

    # print('Barangays without COVID data:', [i for i in qc_df.Barangay if i not in covid_data.Barangay.unique()])

    return df


def create_map(df, filename, total_counts_file, vmax, show_plot=True, save_fig=False, output_dir=None):
    """
    Creates a map showing the number of active cases in Quezon City.

    Args:
        df (dataframe): table containing the peprocessed data
        filename (str): filename of the original data downloaded from QC website
        total_counts_file (dataframe): table containing the total counts per day
        vmax (int): set max value for the colorbar in heatmap
        show_plot (boolean): if set to True, this will display the plot
        savefig (boolean): if set to True, this will save the figure
        output_dir (str): output directory to save file


    Returns:
        None
    """

    # create figure and axes for Matplotlib
    fig, ax = plt.subplots(1, figsize=(15, 12), dpi=500)

    # extract date from file name
    dt = filename.split('/')[-1].replace('-Cases.pdf', '').replace('-', ' ').split(' ')

    # load file of individual count data
    total_counts = pd.read_csv(total_counts_file)

    # extract date from file
    total_counts['Date'] = pd.to_datetime(total_counts['Date'])
    total_counts['Date'] = total_counts['Date'].apply(lambda x: x.strftime('%B %d %Y'))
    total_counts_df = total_counts[total_counts.Date == " ".join(dt)]
    dt[1] = f'{dt[1]},'
    dt = " ".join(dt)

    # set title for map
    ax.set_title(f'                             Quezon city COVID-19 update as of {dt} (8 AM) \n', loc='center',
                 fontdict={'fontsize': '18', 'fontweight':'1'})

    # set color palette for map
    palette = sns.color_palette("flare", as_cmap=True)
    df.plot(column = 'Active', cmap=palette,vmax=vmax, linewidth=0.8, ax=ax, edgecolor='0.8')

    plt.annotate(text='Data source: https://quezoncity.gov.ph', xy=(120.981, 14.582), size=10)

    # annotation
    tot_active = "{:,}".format(int(total_counts_df.Active.values[0]))
    tot_died = "{:,}".format(int(total_counts_df.Deaths.values[0]))
    tot_recov = "{:,}".format(int(total_counts_df.Recoveries.values[0]))
    tot = "{:,}".format(int(total_counts_df.Total.values[0]))

    plt.annotate(text=f'Active: {tot_active}; Deaths: {tot_died}; Recoveries: {tot_recov}; Total: {tot}', xy=(121.0159, 14.7687), size=14)

    # Fairview
    plt.annotate(text=f'Fairview', xy=(120.992, 14.740), size=12)
    plt.annotate(text=f'Active: {"{:,}".format(int(df[df.Barangay == "Fairview"].Active.sum()))}', xy=(120.992, 14.735), size=10)
    plt.annotate(text=f'Died: {"{:,}".format(int(df[df.Barangay == "Fairview"].Died.sum()))}', xy=(120.992, 14.730), size=10)
    plt.annotate(text=f'Recovered: {"{:,}".format(int(df[df.Barangay == "Fairview"].Recovered.sum()))}', xy=(120.992, 14.725), size=10)
    plt.annotate(text=f'Total: {"{:,}".format(int(df[df.Barangay == "Fairview"].Total.sum()))}', xy=(120.992, 14.720), size=10)

    # Commonwealth
    plt.annotate(text=f'Commonwealth', xy=(121.126, 14.716), size=12)
    plt.annotate(text=f'Active: {"{:,}".format(int(df[df.Barangay == "Commonwealth"].Active.values[0]))}', xy=(121.126, 14.711), size=10)
    plt.annotate(text=f'Died: {"{:,}".format(int(df[df.Barangay == "Commonwealth"].Died.values[0]))}', xy=(121.126, 14.706), size=10)
    plt.annotate(text=f'Recovered: {"{:,}".format(int(df[df.Barangay == "Commonwealth"].Recovered.values[0]))}', xy=(121.126, 14.701), size=10)
    plt.annotate(text=f'Total: {"{:,}".format(int(df[df.Barangay == "Commonwealth"].Total.values[0]))}', xy=(121.126, 14.696), size=10)

    # Batasan Hills
    plt.annotate(text=f'Batasan Hills', xy=(121.110, 14.676), size=12)
    plt.annotate(text=f'Active: {"{:,}".format(int(df[df.Barangay == "Batasan Hills"].Active.sum()))}', xy=(121.110, 14.671), size=10)
    plt.annotate(text=f'Died: {"{:,}".format(int(df[df.Barangay == "Batasan Hills"].Died.sum()))}', xy=(121.110, 14.666), size=10)
    plt.annotate(text=f'Recovered: {"{:,}".format(int(df[df.Barangay == "Batasan Hills"].Recovered.sum()))}', xy=(121.110, 14.661), size=10)
    plt.annotate(text=f'Total: {"{:,}".format(int(df[df.Barangay == "Batasan Hills"].Total.sum()))}', xy=(121.110, 14.656), size=10)

    # Holy Spirit
    plt.annotate(text=f'Holy Spirit', xy=(121.090, 14.636), size=12)
    plt.annotate(text=f'Active: {"{:,}".format(int(df[df.Barangay == "Holy Spirit"].Active.sum()))}', xy=(121.090, 14.631), size=10)
    plt.annotate(text=f'Died: {"{:,}".format(int(df[df.Barangay == "Holy Spirit"].Died.sum()))}', xy=(121.090, 14.626), size=10)
    plt.annotate(text=f'Recovered: {"{:,}".format(int(df[df.Barangay == "Holy Spirit"].Recovered.sum()))}', xy=(121.090, 14.621), size=10)
    plt.annotate(text=f'Total: {"{:,}".format(int(df[df.Barangay == "Holy Spirit"].Total.sum()))}', xy=(121.090, 14.616), size=10)

    # Pasong Tamo
    plt.annotate(text=f'Pasong Tamo', xy=(120.985, 14.703), size=12)
    plt.annotate(text=f'Active: {"{:,}".format(int(df[df.Barangay == "Pasong Tamo"].Active.sum()))}', xy=(120.985, 14.698), size=10)
    plt.annotate(text=f'Died: {"{:,}".format(int(df[df.Barangay == "Pasong Tamo"].Died.sum()))}', xy=(120.985, 14.693), size=10)
    plt.annotate(text=f'Recovered: {"{:,}".format(int(df[df.Barangay == "Pasong Tamo"].Recovered.sum()))}', xy=(120.985, 14.688), size=10)
    plt.annotate(text=f'Total: {"{:,}".format(int(df[df.Barangay == "Pasong Tamo"].Total.sum()))}', xy=(120.985, 14.683), size=10)

    # Create colorbar as a legend
    sm = plt.cm.ScalarMappable(cmap=palette, norm=plt.Normalize(vmin=0, vmax=vmax))

    # add the colorbar to the figure
    cbar = fig.colorbar(sm, shrink=0.5, ax = [ax], location = 'right', pad=0.12).ax.set_title('# of active\ncases')

    ax.axis('off')

    if save_fig == True:
        plt.savefig(f"{output_dir}/{filename.split('/')[-1].replace('-Cases.pdf', '')}.png", dpi=500)

    if show_plot != True:
        plt.close()


def batch_process(dt, vmax, data_dir, shapefiles_location, total_counts_file, output_dir):
    """
    Batch processes the data downloaded with an option to create animation
    that visualizes the change in counts temporally.

    Args:
        dt (list of tuples): list of tuples containing the dates that will be considered.
        vmax (int): maximum value for colorbar
        data_dir (str): filepath to the directory containing the downloaded data
        shapefiles_location (str): filepath to the shapefiles
        total_counts_file (str): filepath to the total counts
        output_dir (str): filepath to the output directory
        save_animation (boolean): if set to True, this creates an animation in both 'gif' and 'mp4' formats

    Return:
        None

    """

    for date_range in dt:

        month = date_range[0]
        for day in range(1, date_range[1]+1):
            try:
                if day < 10:
                    downloaded_file = f'{data_dir}/{month}-0{day}-2021-Cases.pdf'
                else:
                    downloaded_file = f'{data_dir}/{month}-{day}-2021-Cases.pdf'

                downloaded_data_df = extract_table(downloaded_file)
                preprocessed_data = preprocess(downloaded_data_df, shapefiles_location)
                create_map(preprocessed_data, downloaded_file, total_counts_file, vmax=vmax,
                   show_plot=False, save_fig=True, output_dir=output_dir)

            except FileNotFoundError:
                continue
