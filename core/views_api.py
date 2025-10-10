from warnings import filters
import requests
from rest_framework import generics, filters
from rest_framework import viewsets
from rest_framework.views import APIView
from .models import CollectionTransfer, Operator, Technician, TypeOfService, WorkFromTheRole, Material, WorkReport, WorkStb
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.contrib.auth.hashers import check_password
from django.contrib.auth import authenticate
from .models import User
from django.conf import settings
from rest_framework import generics, status
from .serializers import CollectionTransferSerializer, UserSerializer, RegisterSerializer, WorkReportSerializer
from rest_framework import status
from django.db.models import Q
from .serializers import (
    OperatorSerializer,
    TechnicianSerializer,
    TypeOfServiceSerializer,
    WorkFromTheRoleSerializer,
    MaterialSerializer,
    WorkStbSerializer
)


# Register User
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

# Login User
class LoginView(APIView):
    def post(self, request):
        identifier = request.data.get("identifier")  # email or phone or name
        password = request.data.get("password")

        try:
            user = User.objects.filter(
                Q(email=identifier) | Q(phone=identifier) | Q(name__iexact=identifier)
            ).first()

            if user and user.check_password(password):
                return Response({
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "phone": user.phone,
                    "alternate_no": user.alternate_no,
                    "whatsapp_no": user.whatsapp_no,
                    "address": user.address,
                    "pincode": user.pincode,
                    "remark": user.remark,
                    "role": user.role,
                    "collection_amount": user.collection_amount,
                    "paid_to_company": user.paid_to_company,
                    "pending_work": user.pending_work,
                    "assigned_work": user.assigned_work,
                    "completed_work": user.completed_work,
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# CRUD for Users
class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class UserRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer



@api_view(['POST'])
def register_user(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def login_user(request):
    phone = request.data.get('phone')
    password = request.data.get('password')

    try:
        user = User.objects.get(phone=phone)
        if check_password(password, user.password):
            return Response({
                "message": "Login successful",
                "user": UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid password"}, status=status.HTTP_400_BAD_REQUEST)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer






# List + Create transfer request (Technician sends to Supervisor)
class CollectionTransferListCreateView(generics.ListCreateAPIView):
    queryset = CollectionTransfer.objects.all().order_by("-id")
    serializer_class = CollectionTransferSerializer


# Accept or Reject transfer (Supervisor action)
class CollectionTransferActionView(APIView):
    def post(self, request, pk):
        action = request.data.get("action")
        remark = request.data.get("remark", "")
        try:
            transfer = CollectionTransfer.objects.get(pk=pk)

            if transfer.status != "Pending":
                return Response({"error": "This request is already processed."}, status=400)

            if action == "accept":
                transfer.accept()
                transfer.remark = remark
                transfer.save()
                return Response({"message": "Transfer accepted successfully."})
            elif action == "reject":
                transfer.reject()
                transfer.remark = remark
                transfer.save()
                return Response({"message": "Transfer rejected."})
            else:
                return Response({"error": "Invalid action."}, status=400)

        except CollectionTransfer.DoesNotExist:
            return Response({"error": "Transfer not found."}, status=404)






class TechnicianViewSet(viewsets.ModelViewSet):
    queryset = Technician.objects.all()
    serializer_class = TechnicianSerializer

class WorkStbViewSet(viewsets.ModelViewSet):
    queryset = WorkStb.objects.all().order_by("-id")
    serializer_class = WorkStbSerializer

    def perform_create(self, serializer):
        # Save the new work
        work = serializer.save()
        # After saving, send WhatsApp message to technician
        self.send_whatsapp_message(work, new=True)

    def perform_update(self, serializer):
        old_work = WorkStb.objects.get(pk=self.get_object().pk)
        work = serializer.save()
        # Check if technician is reassigned
        if old_work.assigned_technician != work.assigned_technician:
            self.send_whatsapp_message(work, new=False)

    def send_whatsapp_message(self, work, new=True):
        technician = work.assigned_technician
        if technician and technician.phone:
            # Build the message
            message_type = "New Work Assigned For You" if new else "Work Reassigned For You"
            msg = f"""
*{message_type}*

Customer: {work.customer_name}
Address: {work.address}
Pincode: {work.pincode}
Mobile: {work.mobile_no}
Alternate: {work.alternate_no or 'N/A'}

Operator: {work.operator.name if work.operator else ''}
Service: {work.type_of_service.name if work.type_of_service else ''}
Work From: {work.work_from.name if work.work_from else ''}
Amount: ₹{work.amount}
Status: {work.status}

Please attend to this work as soon as possible.
"""
            api_token = "02d22c19-69a0-4082-a1fc-46b0e45f6340"
            mobile = f"91{technician.whatsapp_no or technician.phone}"
            url = f"https://whatsbot.tech/api/send_sms"
            params = {
                "api_token": api_token,
                "mobile": mobile,
                "message": msg.strip(),
            }

            try:
                response = requests.get(url, params=params, timeout=10)
                print("WhatsApp message sent:", response.text)
            except Exception as e:
                print("Failed to send WhatsApp message:", e)



class WorkReportListCreateView(generics.ListCreateAPIView):
    queryset = WorkReport.objects.all().order_by("-id")
    serializer_class = WorkReportSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = [
        "work__assigned_technician__id",
        "work__supervisor__id",
        "work__operator__id",
        "work__type_of_service__id",
        "work__work_from__id",
    ]

class WorkReportRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkReport.objects.all()
    serializer_class = WorkReportSerializer










class OperatorViewSet(viewsets.ModelViewSet):
    queryset = Operator.objects.all()
    serializer_class = OperatorSerializer

class TypeOfServiceViewSet(viewsets.ModelViewSet):
    queryset = TypeOfService.objects.all()
    serializer_class = TypeOfServiceSerializer

class WorkFromTheRoleViewSet(viewsets.ModelViewSet):
    queryset = WorkFromTheRole.objects.all()
    serializer_class = WorkFromTheRoleSerializer

class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer






def send_whatsapp_message(mobile, message):
    """
    Send WhatsApp message via whatsbot.tech API.
    mobile should be without country code (we'll prepend '91')
    """
    api_token = "02d22c19-69a0-4082-a1fc-46b0e45f6340"
    full_mobile = f"91{mobile}"
    url = f"https://whatsbot.tech/api/send_sms"
    params = {
        "api_token": api_token,
        "mobile": full_mobile,
        "message": message,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        return response.json()
    except Exception as e:
        print("WhatsApp sending failed:", e)
        return None






