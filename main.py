import random

valid_inputs = ['rock', 'paper', 'scissors']


def user_selection():
    while True:
        print('Rock, Paper, Scissors, GO!')
        human_play = input().lower()
        if human_play in valid_inputs:
            return human_play
        else:
            print()
            print('Please type rock, paper, or scissors')


def computer_selection():
    computer_play = random.choice(valid_inputs)
    return computer_play


def check_result(human_play, computer_play):
    if human_play == computer_play:
        result = "It's a Draw"
    elif (human_play == 'rock' and computer_play == 'scissors') or \
            (human_play == 'paper' and computer_play == 'rock') or \
            (human_play == 'scissors' and computer_play == 'paper'):
        result = "You Win!"
    else:
        result = "Computer Wins!"

    print(result)


def play_again():
    while True:
        response = input("Do you want to play again? (y/n): ").lower()
        if response == 'y':
            return True
        elif response == 'n':
            return False
        else:
            print('Please type "y" or "n".')


def game():
    while True:
        human_play = user_selection()
        computer_play = computer_selection()
        print('You have selected ' + human_play.upper())
        print('The computer has selected ' + computer_play.upper())
        check_result(human_play, computer_play)
        if not play_again():
            break


game()
