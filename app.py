from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os


app = Flask(__name__)

# Конфигурация (убраны CSRF-настройки)
app.config['SECRET_KEY'] = 'ваш-секретный-ключ'  # Оставьте для Flask-Login
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///organizer.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav'}


# Инициализация расширений
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Модели (перенесены из models.py для удобства)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class DiaryEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    mood = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    deadline = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# Маршруты
@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/notes')
@login_required
def notes():
    notes = Note.query.filter_by(user_id=current_user.id).all()
    return render_template('notes.html', notes=notes)


@app.route('/note/<int:id>')
@login_required
def view_note(id):
    note = db.session.get(Note, id)
    if note.user_id != current_user.id:
        flash('У вас нет прав на просмотр этой заметки', 'danger')
        return redirect(url_for('notes'))
    return render_template('view_note.html', note=note)


@app.route('/add_note', methods=['POST'])
@login_required
def add_note():
    title = request.form.get('title')
    content = request.form.get('content')
    new_note = Note(title=title, content=content, user_id=current_user.id)
    db.session.add(new_note)
    db.session.commit()
    flash('Заметка успешно добавлена', 'success')
    return redirect(url_for('notes'))


@app.route('/edit_note/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_note(id):
    note = db.session.get(Note, id)
    if note.user_id != current_user.id:
        flash('У вас нет прав на редактирование', 'danger')
        return redirect(url_for('notes'))

    if request.method == 'POST':
        note.title = request.form.get('title')
        note.content = request.form.get('content')
        db.session.commit()
        flash('Заметка обновлена', 'success')
        return redirect(url_for('view_note', id=note.id))
    return render_template('edit_note.html', note=note)


@app.route('/delete_note/<int:id>', methods=['POST'])
@login_required
def delete_note(id):
    note = db.session.get(Note, id)
    if note.user_id != current_user.id:
        flash('Нет прав на удаление', 'danger')
    else:
        db.session.delete(note)
        db.session.commit()
        flash('Заметка удалена', 'success')
    return redirect(url_for('notes'))


@app.route('/schedule')
@login_required
def schedule():
    events = Schedule.query.filter_by(user_id=current_user.id) \
        .order_by(Schedule.start_time.asc()).all()

    days = {}
    for event in events:
        date_key = event.start_time.strftime('%Y-%m-%d')
        if date_key not in days:
            days[date_key] = []
        days[date_key].append(event)

    # Передаем datetime в шаблон
    return render_template('schedule.html', days=days, datetime=datetime)


@app.route('/add_schedule', methods=['POST'])
@login_required
def add_schedule():
    try:
        start_datetime = datetime.strptime(
            f"{request.form['date']} {request.form['time']}",
            '%Y-%m-%d %H:%M'
        )

        new_event = Schedule(
            title=request.form['title'],
            description=request.form.get('description', ''),
            start_time=start_datetime,
            end_time=start_datetime + timedelta(minutes=30),  # +30 минут по умолчанию
            user_id=current_user.id
        )
        db.session.add(new_event)
        db.session.commit()
        flash('Событие добавлено!', 'success')
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'danger')

    return redirect(url_for('schedule'))


@app.route('/delete_schedule/<int:id>', methods=['POST'])
@login_required
def delete_schedule(id):
    event = db.session.get(Schedule, id)
    if not event or event.user_id != current_user.id:
        flash('Ошибка удаления', 'danger')
    else:
        db.session.delete(event)
        db.session.commit()
        flash('Событие удалено', 'success')
    return redirect(url_for('schedule'))


@app.route('/diary')
@login_required
def diary():
    entries = DiaryEntry.query.filter_by(user_id=current_user.id) \
        .order_by(DiaryEntry.date.desc()).all()
    return render_template('diary.html', entries=entries, current_date=datetime.utcnow().strftime('%Y-%m-%d'))


@app.route('/add_diary_entry', methods=['POST'])
@login_required
def add_diary_entry():
    try:
        new_entry = DiaryEntry(
            title=request.form['title'],
            content=request.form['content'],
            mood=request.form.get('mood'),
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            user_id=current_user.id
        )
        db.session.add(new_entry)
        db.session.commit()
        flash('Запись добавлена!', 'success')
    except Exception as e:
        flash('Ошибка при добавлении записи', 'danger')
    return redirect(url_for('diary'))


@app.route('/diary/<int:id>')
@login_required
def view_diary_entry(id):
    entry = db.session.get(DiaryEntry, id)
    if entry.user_id != current_user.id:
        flash('Нет прав на просмотр', 'danger')
        return redirect(url_for('diary'))
    return render_template('view_diary_entry.html', entry=entry)


@app.route('/delete_diary_entry/<int:id>', methods=['POST'])
@login_required
def delete_diary_entry(id):
    entry = db.session.get(DiaryEntry, id)
    if entry.user_id != current_user.id:
        flash('Нет прав на удаление', 'danger')
    else:
        db.session.delete(entry)
        db.session.commit()
        flash('Запись удалена', 'success')
    return redirect(url_for('diary'))


@app.route('/projects')
@login_required
def projects():
    projects = Project.query.filter_by(user_id=current_user.id).all()
    return render_template('projects.html', projects=projects)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash('Неверный email или пароль', 'danger')
            return redirect(url_for('login'))

        login_user(user, remember=remember)
        return redirect(url_for('index'))

    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('Email уже используется', 'danger')
            return redirect(url_for('register'))

        new_user = User(
            email=email,
            name=name,
            password=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация успешна!', 'success')
        return redirect(url_for('login'))

    return render_template('auth/register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(request.referrer)

    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(request.referrer)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash('Файл загружен', 'success')
    else:
        flash('Недопустимый тип файла', 'danger')

    return redirect(request.referrer)


@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.template_filter('format_date')
def format_date_filter(date_str):
    date = datetime.strptime(date_str, '%Y-%m-%d')
    return date.strftime('%d.%m.%Y (%A)')

@app.template_filter('format_time')
def format_time_filter(dt):
    return dt.strftime('%H:%M')


# Создание базы данных
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)