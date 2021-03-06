from django.shortcuts import render, redirect
from op_tasks.models import UserProfile, Product, Dataset, OpTask, TaskListItem, Experiment
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

from django.http import JsonResponse, HttpResponseForbidden

from op_tasks import tasksUtil

from op_tasks import mechanicalTurk

from op_tasks.surveyMongoUpdate import SM_EXPERIMENT_NAME

from base import ALE_URL
from elasticsearch import Elasticsearch

@login_required(login_url='/tasking/login')
def view_users(request):
	userprofiles = UserProfile.objects.all().order_by('-user__last_login')
	return render(request, 'users.html', {'userprofiles': userprofiles})


@login_required(login_url='/tasking/login')
def manage_users(request):
	userprofiles = UserProfile.objects.all().order_by('-user__last_login')
	return render(request, 'users.html', {'userprofiles': userprofiles})


@login_required(login_url='/tasking/login')
def edit_user(request, userprofilepk):
	userprofile = UserProfile.objects.get(id=userprofilepk)
	experiment = Experiment.objects.get(name=request.POST['experiment_name'])
	userprofile.experiment = experiment
	userprofile.save()

	return redirect('exp_portal:view_users')


@login_required(login_url='/tasking/login')
def add_user(request):
	experiments = Experiment.objects.all()
	products = Product.objects.all()
	return render(request, 'add_user.html', {'experiments': experiments, 'products':products})


@login_required(login_url='/tasking/login')
def delete_user(request, userprofilepk):
	userprofile = UserProfile.objects.get(id=userprofilepk)
	user = userprofile.user
	usertasks = userprofile.tasklistitem_set.all()

	for tasklistitem in usertasks:
		tasklistitem.delete()

	user.delete()
	userprofile.delete()

	return redirect('exp_portal:view_users')


@login_required(login_url='/tasking/login')
def new_user(request):
    user = get_user_model()(email=request.POST['email'])
    user.set_password(request.POST['password_1'])
    user.last_login = '1970-01-01 00:00'
    user.save()

    userprofile = UserProfile()
    userprofile.user = user
    experiment = Experiment.objects.get(name=request.POST['experiment_name'])
    userprofile.experiment = experiment
    userprofile.save()

    # logic for assigning tasks
    if request.POST['product_name'] == 'all':
        # all products all tasks buffet style
		tasksUtil.appendAllTasks(user)
    else:
		# single product - task ordering assumed
		product = Product.objects.get(name=request.POST['product_name'])
		if str(request.POST['taskorder']) == 'b':
			print 'true'
			tasks = product.dataset.optask_set.all().order_by('id').reverse()
		else:
			tasks = product.dataset.optask_set.all().order_by('id')

		tasks = tasks.filter(is_active=True)

		index = 0
		for task in tasks:
			newtasklistitem = TaskListItem()
			newtasklistitem.userprofile = userprofile
			newtasklistitem.op_task = task
			newtasklistitem.product = product
			newtasklistitem.index = index
			# if index == 0 or experiment.sequential_tasks == False:
			# 	newtasklistitem.task_active = True
			# else:
			# 	newtasklistitem.task_active = False
			index = index + 1
			newtasklistitem.save()

    return redirect('exp_portal:view_users')


@login_required(login_url='/tasking/login')
def user_added(request):
	return render(request, 'user_added.html')


@login_required(login_url='/tasking/login')
def view_user_tasks(request, profile):
	userprofile = UserProfile.objects.all().filter(user_hash=profile)[0]
	usertasks = userprofile.tasklistitem_set.all()
	experiments = Experiment.objects.all()
	
	datasets = Dataset.objects.all()
	count = 0
	tasklistitems = []
	for dataset in datasets:
		for product in dataset.product_set.all():
			for task in dataset.optask_set.all():
				count = count + 1

	return render(request, 'user_tasks.html', {'userprofile': userprofile, 'experiments':experiments})


@login_required(login_url='/tasking/login')
def add_user_task(request, userpk):
	userprofile = UserProfile.objects.get(id=userpk)
	datasets = Dataset.objects.all()
	products = Product.objects.all()
	tasks = OpTask.objects.all()
	return render(request, 'add_user_task.html', {'userprofile':userprofile, 
		'datasets': datasets, 'products': products, 'tasks': tasks})


@login_required(login_url='/tasking/login')
def update_user_tasks(request, userpk, datasetpk, productpk, taskpk):
	dataset = Dataset.objects.get(id=datasetpk)
	userprofile = UserProfile.objects.get(id=userpk)
	index = userprofile.tasklistitem_set.count()

	newtasklistitem = TaskListItem()
	newtasklistitem.userprofile = userprofile
	newtasklistitem.op_task = OpTask.objects.get(id=taskpk)
	newtasklistitem.product = Product.objects.get(id=productpk)
	newtasklistitem.index = index
	newtasklistitem.task_active = True
	newtasklistitem.save()

	return redirect('exp_portal:add_user_task', userpk)

def view_users_experiment(request, experiment_name):
        print "Experiment User Request From: ", request.META['REMOTE_ADDR']
        if request.META['REMOTE_ADDR'] != '127.0.0.1':
            return HttpResponseForbidden()

	experiment = Experiment.objects.get(name=experiment_name)
	userprofiles = experiment.userprofile_set.all()
	user_hashes = {}
	for userprofile in userprofiles:
               tasklistitems = userprofile.tasklistitem_set.all()
               completedTasks = [task for task in tasklistitems if task.task_complete is True]

               #Mechanical Turk task completion payment code
	       mtcode = mechanicalTurk.generateCode(userprofile.user.id,userprofile.user_hash)

               if userprofile.intake_complete == 1:
                        session_id = str(userprofile.user_hash)+'::0'

			stoutVars = {'SYS.FIL.DAT.':'',
                                     'SYS.FIL.EXP.':SM_EXPERIMENT_NAME,
                                     'SYS.FIL.APP.':'',
                                     'SYS.FIL.TSK.':'INTAKE',
                                     'SYS.FIL.ORD.':'',
                                     'SYS.FIL.STD.':''}
			user_hashes[session_id]={'mtcode':mtcode,'vars':stoutVars}	
               for task in completedTasks:
                        #unique identifier for user::task
                        session_id = str(userprofile.user_hash)+'::'+str(task.pk)
                        #TEST VALUE
                        #session_id = "49bacc695d39a2f23cf44f949409e7::1104"

                        #ALE logged survey start time
                        XDATA_INDEX="xdata_v3"
                        es = Elasticsearch(ALE_URL)
                        queryData = {}
                        fieldFilter = ["timestamp", "sessionID", "elementId"]
                        sMatch = {"match" : {"sessionID" : session_id}}
                        eMatch = {"match" : {"elementId" : "open_task_button"}}
                        mustField = [sMatch, eMatch]
                        queryData["query"] = { "bool": { "must" : mustField } }
                        results = es.search(index=XDATA_INDEX, body=queryData, fields=fieldFilter, size=1000)['hits']
                        timestamps = [d['fields']['timestamp'] for d in results['hits']]

                        #ES WILL BE BLOCKED SOON.  INSTEAD:
                        #results = requests.get(ALE_URL + "/" + XDATA_INDEX + "/select?q=sessionID:" + sessionID + "&q=elementID:open_task_button&fl=timestamp,sessionID,elementID&size=1000")

                        if len(timestamps) > 1:
                            print "Warning, more than 1 timestamp from Elastic"
                        if len(timestamps) < 1:
                            print "Warning, no timestamp from Elastic"
                            timestamps = [["NA"]]
                        print "Elastic result: ", timestamps
			#print "Timestamp: ", timestamps[0][0], "; Type: ", type(timestamps[0][0])

			stoutVars = {'SYS.FIL.DAT.':task.op_task.dataset.name,
                                     'SYS.FIL.EXP.':SM_EXPERIMENT_NAME,
                                     'SYS.FIL.APP.':task.product.name,
                                     'SYS.FIL.TSK.':task.op_task.name,
                                     'SYS.FIL.ORD.':str(task.index),
                                     'SYS.FIL.STD.':timestamps[0][0]}
			user_hashes[session_id]={'mtcode':mtcode,'vars':stoutVars}	

	response = JsonResponse(user_hashes, safe=False)
	return response
