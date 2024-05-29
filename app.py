from flask import Flask, render_template, request, redirect, url_for

import os
import pandas as pd
from datetime import datetime
import pytz
import requests

app = Flask(__name__)

#############

def process_api_ratings(api_ratings):
    # [{'Source': '', 'Value': ''}, {'Source': '', 'Value': ''}]
    ratings = [] # correct rating should be int from 0 to 100
    for rating in api_ratings:
        if rating['Source'] == 'Internet Movie Database':
            # these ratings are by general public, not critics, so do not count
            continue
        value = rating['Value'] 
        if value[-1] == '%': # '94%'
            ratings.append(int(value[:-1]))
        elif value.split('/')[1] == '100': # '94/100'
            ratings.append(int(value.split('/')[0]))
        elif value.split('/')[1] == '10': # '9.4/10'
            ratings.append(int(10*float(value.split('/')[0])))
    return ratings

class MovieDatabase:
    def __init__(self):
        self.filename = os.path.join('data', 'movies.csv')
        if not os.path.exists(self.filename):
            df = pd.DataFrame(columns=['Filma', 'Kritiķu vērtējums'])
            df.to_csv(self.filename, index=False)
        self.data = pd.read_csv(self.filename)

    def add_movie_to_movies_db(self, movie, critics_rating):
        if movie not in self.data['Filma'].values:
            new_row = pd.DataFrame([{
                'Filma': movie,
                'Kritiķu vērtējums': critics_rating
            }])
            self.data = pd.concat([self.data, new_row], ignore_index=True)
            self.data.to_csv(self.filename, index=False)

    def request_critics_rating(self, title, year):
        # https://www.omdbapi.com/?t=Harry+Potter&y=2001&apikey=51f2a4ee
        # Harry Potter (2001)
        try:
            if year == '':
                response = requests.get(url='https://www.omdbapi.com/', 
                                        params={'t': '+'.join(title.split()), 'apikey': '51f2a4ee'}).json()
            else:
                response = requests.get(url='https://www.omdbapi.com/', 
                                        params={'t': '+'.join(title.split()), 'y': year, 'apikey': '51f2a4ee'}).json()
            correct_title = response["Title"]
            correct_year = int(response["Year"])
            correct_title = f'{correct_title} ({correct_year})'
            ratings = process_api_ratings(response['Ratings'])
            critics_rating = round(sum(ratings)/len(ratings))
            self.add_movie_to_movies_db(correct_title, critics_rating)
        except:
            correct_title = None
            critics_rating = None
        return correct_title, critics_rating

movies = MovieDatabase()

class RatingDatabase:
    def __init__(self):
        self.filename = os.path.join('data', 'ratings.csv')
        if not os.path.exists(self.filename):
            df = pd.DataFrame(columns=['Laiks', 'Lietotājs', 'Filma', 'Lietotāja vērtējums', 'Kritiķu vērtējums'])
            df.to_csv(self.filename, index=False)
        self.data = pd.read_csv(self.filename)

    def add_movie_to_ratings_db(self, user, movie, user_rating, critics_rating):
        time = datetime.now(pytz.timezone('Europe/Riga')).strftime('%d.%m.%Y. %H:%M')
        if not ( (user in self.data['Lietotājs'].values) and (movie in self.data['Filma'].values) ):
            new_row = pd.DataFrame([{
                'Laiks': time,
                'Lietotājs': user,
                'Filma': movie,
                'Lietotāja vērtējums': int(user_rating),
                'Kritiķu vērtējums': critics_rating
            }])
            self.data = pd.concat([self.data, new_row], ignore_index=True)
        else:
            existing_row = self.data[(self.data['Lietotājs']==user) & (self.data['Filma']==movie)]
            existing_row['Laiks'] = time
            existing_row['Lietotāja vērtējums'] = int(user_rating)
            idx = existing_row.index[0]
            # existing_row = self.data.loc[idx]
            self.data = self.data.drop(idx)
            self.data = pd.concat([self.data, existing_row], ignore_index=True)
        self.data.to_csv(self.filename, index=False)

    def get_summary(self):
        user_rating_avg = str(round(self.data['Lietotāja vērtējums'].mean(), 1))
        critics_rating_avg = str(round(self.data['Kritiķu vērtējums'].mean(), 1))
        return user_rating_avg, critics_rating_avg

ratings = RatingDatabase()


#############


@app.route('/')
def sākums():
    return render_template('sākums.html', current_page='sākums')



@app.route('/par_mums')
def par_mums():
    return render_template('par_mums.html', current_page='par_mums')



@app.route('/vērtē')
def vērtē():
    error = request.args.get('error', 'False') == 'True'
    return render_template('vērtē.html', current_page='vērtē', error=error)

@app.route("/salīdzini", methods=['GET', 'POST'])
def salīdzini():
    if request.method == 'GET':
        data = ratings.data[:-11:-1]
        data = data.values.tolist()
    else:
        user = request.form.get('user')
        movie = request.form.get('movie')
        year = request.form.get('year')
        user_rating = request.form.get('user_rating')
        movie, critics_rating = movies.request_critics_rating(movie, year)
        if movie is None:
            return redirect(url_for('vērtē', error=True))
        ratings.add_movie_to_ratings_db(user, movie, user_rating, critics_rating)
        data = ratings.data.iloc[-1, :]
        data = [data.values.tolist()]
    return render_template('salīdzini.html', current_page='salīdzini', data=data)

@app.route('/pārskats')
def pārskats():
    user_rating_avg, critics_rating_avg = ratings.get_summary()
    return render_template('pārskats.html', current_page='pārskats', 
                           user_rating_avg=user_rating_avg, critics_rating_avg=critics_rating_avg)
