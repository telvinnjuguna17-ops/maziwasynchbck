from django.shortcuts import render
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import IsAdminUser,AllowAny

from rest_framework import viewsets
from rest_framework.views import APIView

from cooperative.serializer import FarmerSerializer, MilkCollectionSerializer, NoticeSerializer, PorterSerializer
from cooperative.services import MpesaPayment
from core.models import FarmerProfile, Feedback, MilkCollection, Notice, Payment, PorterProfile
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from rest_framework.response import Response

# admin dashboard
class AdminDashboardView(APIView):
    # only admin can access the analystics dashboard
    permission_classes=[IsAdminUser]

    # Method to get the analystics
    def get(self,request):
        # define the dates according to django timezone settings
        # used for the daily,weekly and monthly calculations
        today=timezone.localdate()
        # calculate the weekly which is 7 days
        week_start= today-timedelta(days=7)

        # farmer and porters stats
        total_farmers=FarmerProfile.objects.count()
        total_porters=PorterProfile.objects.count()

        # milk collection stats
        # we retrive all the collections so that we can reuse
        collections=MilkCollection.objects.all()

        total_liters=collections.aggregate(total=Sum('liters'))['total'] or 0
        # todays collections
        today_liters=collections.filter(collection_date=today).aggregate(
            total=Sum('liters')

        )['total'] or 0
        # weekly collections
        weekly_liters=collections.filter(collection_date__gte=week_start).aggregate(
            total=Sum('liters')
        )['total'] or 0

        # monthly collections
        monthly_liters=collections.filter(
            collection_date__year=today.year,
            collection_date__month=today.month).aggregate(total=Sum('liters'))['total'] or 0
        
        # REVENUE STATS
        # total revenue
        total_revenue=collections.aggregate(total=Sum('total_amount'))['total'] or 0

        # todays revenue
        today_revenue=collections.filter(collection_date=today).aggregate(total=Sum('total_amount'))['total'] or 0

        # weekly revenue
        weekly_revenue=collections.filter(collection_date__gte=week_start).aggregate(
            total=Sum('total_amount')
        )['total'] or 0

        # monthly revenue
        monthly_revenue=collections.filter(
            collection_date__year=today.year,
            collection_date__month=today.month).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # feedback analystics
        feedbacks=Feedback.objects.all()
        # total feedbacks
        total_feedbacks=feedbacks.count()

        # resolved feedbacks
        resolved_feedbacks=feedbacks.filter(status='RESOLVED').count()

        # pending feedbacks
        pending_feedbacks=feedbacks.filter(status='PENDING').count()

        # rejected feedbacks
        rejected_feedbacks=feedbacks.filter(status='REJECTED').count()

        # Top farmers- retrive farmers with highest milk delivered
        top_farmers=FarmerProfile.objects.order_by(
            '-total_milk_delivered'
        )[:5]
        
        # convert the object inti json form
        # response cannot directly return the Django model objects 
        top_farmers_data=FarmerSerializer(
            top_farmers,
            many=True
        ).data

        # Top ten latest milk collection
        recent_collection=MilkCollection.objects.select_related(
            'farmer',
            'porter'
        ).order_by('-created_at')[:10]
        
        # convert the objects into the json data
        recent_collection_date=MilkCollectionSerializer(
            recent_collection,
            many=True
        ).data

        # dashboard response
        # send all the analytic data to the frontend

        return Response({
            'farmers':total_farmers,
            'porters':total_porters,
            'total_liters': total_liters,
            'today_liters': today_liters,
            'weekly_liters': weekly_liters,
            'monthly_liters': monthly_liters,
            'total_revenue': total_revenue,
            'today_revenue': today_revenue,
            'weekly_revenue': weekly_revenue,
            'monthly_revenue': monthly_revenue,
            'total_feedbacks':total_feedbacks,
            'rejected_feedbacks':rejected_feedbacks,
            'resolved_feedbacks':resolved_feedbacks,
            'pending_feedbacks':pending_feedbacks,
            'recent_collections':recent_collection_date,
            'top_farmers':top_farmers_data

        })






 
# Create your views here.
class FarmerViewSet(viewsets.ModelViewSet):
    queryset=FarmerProfile.objects.all()
    serializer_class=FarmerSerializer
    permission_classes=[IsAdminUser]
    http_method_names=['get','put','patch','delete']



#Create the porters viewset
class PorterViewSet(viewsets.ModelViewSet):
    queryset= PorterProfile.objects.all() 
    serializer_class=PorterSerializer
    permission_classes=[IsAdminUser]
    http_method_names=['get','put','patch','delete']


#create the milkcollection viewset
class MilkCollectionViewSet(viewsets.ModelViewSet):
    queryset=MilkCollection.objects.select_related(
        'farmer',
        'porter'

    )
    serializer_class=MilkCollectionSerializer
    permission_classes=[IsAdminUser]
    http_method_names=['get','put','patch','delete']


#  Notices board by the cooperative 
class NoticeViewSet(viewsets.ModelViewSet):
    queryset=Notice.objects.all()  
    serializer_class=NoticeSerializer
    permission_classes=[IsAdminUser]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# Farmers with outstanding balances
@api_view(['GET'])
@permission_classes([IsAdminUser])
def FarmersWithBal(request):
    farmers=FarmerProfile.objects.all()
    data=[]
    for farmer in farmers:
        # amount earned by the farmer
        earned=MilkCollection.objects.filter(farmer=farmer).aggregate(
            total=Sum('total_amount')
        )['total'] or 0

        # amount paid to the farmer
        paid=Payment.objects.filter(farmer=farmer,status='COMPLETED').aggregate(
            total=Sum('amount')
        )['total'] or 0

        balance=earned-paid
        if balance>0:
            data.append({
                "farmer_id":farmer.id,
                "farmer":f"{farmer.first_name} {farmer.last_name}",
                "phone":farmer.phone_number,
                "earned":earned,
                "balance":balance
            })

    return Response(data)       


# Initialize the disbursment to the farmer
@api_view(['POST'])
@permission_classes([IsAdminUser])
def Pay_farmer(request):
    farmer_id=request.data.get("farmer_id")
    amount=request.data.get("amount")

    farmer=FarmerProfile.objects.get(id=farmer_id)

    earned=MilkCollection.objects.filter(farmer=farmer).aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    paid=Payment.objects.filter(farmer=farmer,status='COMPLETED').aggregate(
        total=Sum('amount')
    )['total'] or 0
    balance=earned-paid
    
    # Prevent paying a farmer who has no pending balance
    if balance<=0:
        return Response({"message":"No pending payment"})
    
    # creating an object from MPESAPAYMENT class in our services.py
    payment=MpesaPayment()
    result=payment.pay_farmer(farmer.phone_number,amount)

    # create the payment record
    Payment.objects.create(
        farmer=farmer,
        amount=amount,
        payment_method="MPESA",
        originator_conversation_id=result['OriginatorConversationID'],
        transaction_ref=result['ConversationID'],
        payment_date=timezone.now()
    )

    return Response({
        'farmer':f"{farmer.first_name} {farmer.last_name}",
        'previous_balance':balance,
        'mpesa_response':result
    })



# Asynchronous callback processind webhook
@api_view(['POST'])
@permission_classes([AllowAny])
def MpesaCallback(request):
    print('=========Call back Hit==========')
    data=request.data


    # print the response from safaricom to see it inthe terminal
    print("Data",data)
    result=data["Result"]

    originator_conversation_id=result["OriginatorConversationID"]

    # retrive the matching payment record with the originator conversation id
    payment=Payment.objects.get(originator_conversation_id=originator_conversation_id)

    # check if the transaction was successful
    if result["ResultCode"]==0:
        payment.status="COMPLETED"
        payment.transaction_ref = result.get("TransactionID", "")
    else:
        payment.status="FAILED"

    payment.save()
    return Response({"recieved":True})        