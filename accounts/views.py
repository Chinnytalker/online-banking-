from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.core.paginator import Paginator
import logging
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse





from .forms import UserRegistrationForm, MessageForm
from .models import BankAccount, Message, VerificationToken, Transaction, CardRequest, User

# Logger setup
logger = logging.getLogger(__name__)



def index(request):
    logger.debug(f"Index page accessed by user: {request.user}")
    logger.info(f"{request.user.username} did X from IP: {request.META.get('REMOTE_ADDR')}")
    return render(request, 'accounts/index.html')


def register(request):
    if request.user.is_authenticated and not request.user.is_superuser:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            if User.objects.filter(email=form.cleaned_data['email']).exists():
                messages.error(request, "Email already exists.")
                return redirect('register')
            if User.objects.filter(username=form.cleaned_data['username']).exists():
                messages.error(request, "Username already exists.")
                return redirect('register')

            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])

            # ✅ Make account active immediately
            user.is_active = True
            user.email_verified = True  # Remove this line if your User model doesn't use it
            user.save()

            try:
                BankAccount.objects.create(user=user, account_type='Savings')
            except Exception as e:
                logger.error(f"Error creating bank account for user {user.username}: {e}")
                user.delete()
                messages.error(request, "Error creating bank account. Please try again.")
                return redirect('register')

            # ✅ Remove email verification logic
            messages.success(request, "Registration successful! You can now log in.")
            return redirect('login')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


# def send_verification_email(request, user):
#     try:
#         token, _ = VerificationToken.objects.get_or_create(user=user)
#         verification_link = request.build_absolute_uri(reverse('verify_email', args=[token.token]))
#         subject = 'Verify Your Email'
#         html_message = render_to_string('accounts/email_verification.html', {
#             'user': user,
#             'verification_link': verification_link,
#         })
#         email = EmailMessage(
#             subject,
#             html_message,
#             settings.DEFAULT_FROM_EMAIL,
#             [user.email],
#         )
#         email.content_subtype = 'html'
#         email.send(fail_silently=False)
#     except Exception as e:
#         logger.error(f"Failed to send email to {user.email}: {e}", exc_info=True)
#         raise e  # re-raise to be caught in register view



# def verify_email(request, token):
#     try:
#         verification_token = VerificationToken.objects.get(token=token)
#         user = verification_token.user
#         user.email_verified = True
#         user.is_active = True
#         user.save()
#         verification_token.delete()
#         messages.success(request, "Your email has been verified successfully! You can now log in.")
#         return redirect('login')
#     except VerificationToken.DoesNotExist:
#         messages.error(request, "Invalid or expired verification link.")
#         return redirect('index')


def login_view(request):
    if request.user.is_authenticated and not request.user.is_superuser:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # ✅ Remove email verification check
            # if not user.email_verified:
            #     return render(request, 'accounts/login.html', {
            #         'form': form,
            #         'error': 'Please verify your email before logging in.'
            #     })

            login(request, user)

            # Check if bank account exists, but skip for superusers
            bank_account = None
            if not user.is_superuser:
                try:
                    bank_account = BankAccount.objects.get(user=user)
                except BankAccount.DoesNotExist:
                    messages.error(request, "Bank account not found. Please contact support.")
                    return redirect('index')

            # Notify user if account is frozen, but allow login
            if not user.is_superuser and bank_account:
                if bank_account.status == "Frozen":
                    messages.warning(
                        request,
                        "Your account is currently frozen. Some features may be restricted. "
                        "<a href='{0}'>Contact admin</a> if you believe this is a mistake.".format(reverse('send_message')),
                        extra_tags='safe'
                    )

            return redirect('dashboard')
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})




def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('index')


@login_required
def dashboard(request):
    # Block superusers from accessing dashboard
    if request.user.is_superuser:
        messages.error(request, "Superusers cannot access the user dashboard.")
        return redirect('index')
    try:
        account = BankAccount.objects.get(user=request.user)
    except BankAccount.DoesNotExist:
        messages.error(request, "Bank account not found. Please contact support.")
        return redirect('index')

    # If account is frozen, show clear warning and allow messaging admin
    if account.status == "Frozen":
        messages.warning(
            request,
            "Your account is currently frozen. Some features may be restricted. please Contact Admin to unfreeze your Account."
        )

    messages_list = Message.objects.filter(user=request.user).order_by('-created_at')[:10]
    unread_messages = Message.objects.filter(user=request.user, read=False).order_by('-created_at')
    unread_count = unread_messages.count()

    # Mark all unread messages as read when dashboard is loaded
    if unread_count > 0:
        unread_messages.update(read=True)
    transactions = Transaction.objects.filter(account=account).order_by('-date')[:10] if account else []
    card_requests = CardRequest.objects.filter(user=request.user).order_by('-date_requested')

    # Handle sending a message to admin
    if request.method == 'POST':
        if 'withdraw' in request.POST:
            with transaction.atomic():
                account.status = "Frozen"
                account.save()
            logger.info(f"Account {account.account_number} frozen by {request.user.username}.")
            messages.success(request, "Your account has been frozen for withdrawal.")
            return redirect('dashboard')

        elif 'request_card' in request.POST:
            CardRequest.objects.create(user=request.user, status='pending')
            logger.info(f"Card request submitted by {request.user.username}.")
            messages.success(request, "Your card request has been submitted.")
            return redirect('dashboard')

        elif 'deposit' in request.POST:
            if account.status == "Frozen":
                messages.error(request, "Your account is currently frozen. You cannot deposit funds. <a href='{}'>Contact admin</a> if you believe this is a mistake.".format(reverse('send_message')), extra_tags='safe')
                return redirect('dashboard')
            return redirect('deposit')

        elif 'transfer' in request.POST:
            if account.status == "Frozen":
                messages.error(request, "Your account is currently frozen. You cannot transfer funds. <a href='{}'>Contact admin</a> if you believe this is a mistake.".format(reverse('send_message')), extra_tags='safe')
                return redirect('dashboard')
            return redirect('transfer_money')

        elif 'reply_to' in request.POST:
            reply_to_id = request.POST.get('reply_to')
            reply_content = request.POST.get('reply_content')

            if reply_to_id and reply_content:
                try:
                    parent_message = Message.objects.get(id=reply_to_id, user=request.user)
                    Message.objects.create(
                        user=request.user,
                        sender=request.user.username,
                        content=reply_content,
                        parent=parent_message
                    )
                    logger.info(f"User {request.user.username} replied to message ID {reply_to_id}.")
                    messages.success(request, "Reply sent.")
                except Message.DoesNotExist:
                    messages.error(request, "Original message not found.")
            else:
                messages.error(request, "Reply failed. Content missing.")
            return redirect('dashboard')

        elif 'send_admin_message' in request.POST:
            admin_message = request.POST.get('admin_message')
            if admin_message:
                Message.objects.create(
                    user=request.user,
                    sender=request.user.username,
                    content=admin_message
                )
                logger.info(f"User {request.user.username} sent a message to admin.")
                messages.success(request, "Your message has been sent to the admin.")
            else:
                messages.error(request, "Message content cannot be empty.")
            return redirect('dashboard')

    return render(request, 'accounts/dashboard.html', {
        'account': account,
        'messages': messages_list,
        'transactions': transactions,
        'card_requests': card_requests,
        'unread_messages': unread_messages,
        'unread_count': unread_count,
    })


@login_required
def transfer_money(request):
    if request.method == 'POST':
        receiver_account_number = request.POST.get('receiver_account')
        try:
            amount = float(request.POST.get('amount'))
            if amount <= 0:
                raise ValueError("Amount must be positive.")
        except ValueError:
            return render(request, 'accounts/transfer.html', {'error': 'Invalid amount.'})

        sender_account = BankAccount.objects.get(user=request.user)
        receiver_account = get_object_or_404(BankAccount, account_number=receiver_account_number)

        if sender_account == receiver_account:
            return render(request, 'accounts/transfer.html', {'error': 'Cannot transfer to the same account.'})

        if sender_account.balance < amount:
            return render(request, 'accounts/transfer.html', {'error': 'Insufficient balance.'})

        with transaction.atomic():
            sender_account.balance -= amount
            receiver_account.balance += amount
            sender_account.save()
            receiver_account.save()

        send_mail(
            subject="Transfer Notification",
            message=(
                f"Dear {request.user.first_name},\n\n"
                f"You have successfully transferred ${amount:.2f} to account {receiver_account_number}.\n\n"
                "Thank you for using our services.\n\nBest regards,\nYour Bank"
            ),
            from_email="skybank604@gmail.com",
            recipient_list=[request.user.email],
            fail_silently=False,
        )

        logger.info(f"User {request.user.username} transferred ${amount:.2f} to account {receiver_account_number}.")
        messages.success(request, "Transfer successful!")
        return redirect('dashboard')

    return render(request, 'accounts/transfer.html')


@login_required
def user_messages(request):
    messages_list = Message.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(messages_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'accounts/messages.html', {'page_obj': page_obj})


@login_required
def send_message(request):
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.user = request.user
            message.sender = 'User'
            message.save()
            logger.info(f"Message sent by {request.user.username}.")
            messages.success(request, "Your message has been sent to the admin.")
            return redirect('user_messages')
    else:
        form = MessageForm()
    return render(request, 'accounts/send_message.html', {'form': form})


@login_required
def top_up(request):
    if request.user.is_superuser:
        messages.error(request, "Superusers cannot access the top-up page.")
        return redirect('index')
    try:
        account = BankAccount.objects.get(user=request.user)
    except BankAccount.DoesNotExist:
        messages.error(request, "Bank account not found. Please contact support.")
        return redirect('index')
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount'))
            if amount <= 0:
                raise ValueError("Invalid amount")
        except (ValueError, TypeError):
            messages.error(request, "Invalid top-up amount.")
            return redirect('top_up')


        account.balance += amount
        account.save()

        transaction = Transaction.objects.create(
            account=account,
            amount=amount,
            type='credit',
            description='Top-up from external source'
        )

        # Send top-up notification email
        from django.utils import timezone
        html_message = render_to_string('accounts/topup_notification.html', {
            'user': request.user,
            'amount': amount,
            'account': account,
            'date': timezone.now(),
            'description': transaction.description,
            'new_balance': account.balance,
            'now': timezone.now(),
        })
        email = EmailMessage(
            subject="Account Top-Up Notification",
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[request.user.email],
        )
        email.content_subtype = 'html'
        email.send(fail_silently=True)

        messages.success(request, f"${amount:.2f} has been added to your account via top-up.")
        return redirect('dashboard')

    return render(request, 'accounts/top_up.html', {'account': account})




@login_required
def deposit(request):
    if request.user.is_superuser:
        messages.error(request, "Superusers cannot access the deposit page.")
        return redirect('index')
    try:
        account = BankAccount.objects.get(user=request.user)
    except BankAccount.DoesNotExist:
        messages.error(request, "Bank account not found. Please contact support.")
        return redirect('index')
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount'))
            if amount <= 0:
                raise ValueError("Invalid amount")
        except (ValueError, TypeError):
            messages.error(request, "Invalid deposit amount.")
            return redirect('deposit')


        account.balance += amount
        account.save()

        transaction = Transaction.objects.create(
            account=account,
            amount=amount,
            type='credit',
            description='Cash deposit'
        )

        # Send deposit notification email
        from django.utils import timezone
        html_message = render_to_string('accounts/topup_notification.html', {
            'user': request.user,
            'amount': amount,
            'account': account,
            'date': timezone.now(),
            'description': transaction.description,
            'new_balance': account.balance,
            'now': timezone.now(),
        })
        email = EmailMessage(
            subject="Account Deposit Notification",
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[request.user.email],
        )
        email.content_subtype = 'html'
        email.send(fail_silently=True)

        messages.success(request, f"${amount:.2f} has been deposited to your account.")
        return redirect('dashboard')

    return render(request, 'accounts/deposit.html', {'account': account})




@login_required
def transaction_history(request):
    if request.user.is_superuser:
        messages.error(request, "Superusers cannot access the transaction history page.")
        return redirect('index')
    try:
        account = BankAccount.objects.get(user=request.user)
    except BankAccount.DoesNotExist:
        messages.error(request, "Bank account not found. Please contact support.")
        return redirect('index')
    transactions = Transaction.objects.filter(account=account).order_by('-date')
    paginator = Paginator(transactions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'accounts/transaction_history.html', {'page_obj': page_obj})


def privacy_policy(request):
    return render(request, 'accounts/privacy_policy.html')
