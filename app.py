from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from pypdf import PdfReader
import secrets
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"  # folder where uploaded files are saved temporarily
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

# Session configuration:
# Flask uses a `SECRET_KEY` to sign session cookies so the server can
# trust that the data in the cookie wasn't tampered with by the browser.
# In production, set the `SECRET_KEY` via an environment variable and keep
# it secret. Here we fall back to a simple development key when not set.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")


def allowed_file(filename):
    """Return True when the uploaded file has an allowed file extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_page_count(file_path, filename):
    """Return the printable page count for an uploaded document."""
    extension = filename.rsplit(".", 1)[1].lower()
    if extension != "pdf":
        return 1

    reader = PdfReader(file_path, strict=False)
    page_count = len(reader.pages)
    if page_count < 1:
        raise ValueError("The uploaded PDF contains no pages.")
    return page_count


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    error = None

    if request.method == "POST":
        # Read the uploaded file from the form field named 'document'
        uploaded_file = request.files.get("document")

        if uploaded_file and uploaded_file.filename and allowed_file(uploaded_file.filename):
            filename = secure_filename(uploaded_file.filename)
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            uploaded_file.save(save_path)

            try:
                page_count = get_page_count(save_path, filename)
            except Exception:
                try:
                    os.remove(save_path)
                except OSError:
                    pass
                error = "We could not read that file. Please upload a valid, non-empty PDF or image."
                return render_template("upload.html", error=error)

            # Store only the secure filename in the user's session so
            # later pages (like settings or summary) know which file
            # belongs to this user's job. We do NOT store file contents
            # in the session — the file itself remains on disk in uploads/.
            session["uploaded_filename"] = filename
            session["number_of_pages"] = page_count
            return redirect(url_for("settings"))

        error = "Please select a valid PDF, JPG/JPEG, or PNG file."

    return render_template("upload.html", error=error)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        copies_raw = request.form.get("copies", "1")
        print_type = request.form.get("print_type")
        paper_size = request.form.get("paper_size")
        orientation = request.form.get("orientation", "portrait")
        pages_per_sheet = request.form.get("pages_per_sheet", "1")
        print_sides = request.form.get("print_sides", "single")

        # Validate the copies value safely so the app does not crash if
        # the submitted value is missing or not an integer.
        try:
            copies = int(copies_raw)
            if copies < 1:
                copies = 1
        except (TypeError, ValueError):
            copies = 1

        # Price mapping based on paper size and print type.
        # These are temporary prototype rates and can be replaced later.
        price_per_page_map = {
            ("a4", "bw"): 2,
            ("a4", "color"): 5,
            ("a3", "bw"): 10,
            ("a3", "color"): 20,
        }

        price_per_page = price_per_page_map.get((paper_size, print_type), 2)

        number_of_pages = session.get("number_of_pages") or 1

        total_price = number_of_pages * copies * price_per_page

        # Store the selected settings and calculated price values in the
        # session so later pages can render the order summary and payment
        # information without requiring the user to re-submit the form.
        session["copies"] = copies
        session["print_type"] = print_type
        session["paper_size"] = paper_size
        session["orientation"] = orientation
        session["pages_per_sheet"] = pages_per_sheet
        session["print_sides"] = print_sides
        session["price_per_page"] = price_per_page
        session["number_of_pages"] = number_of_pages
        session["total_price"] = total_price

        return redirect(url_for("summary"))

    return render_template("print_settings.html")


@app.route("/summary")
def summary():
    """Order summary page.

    Reads the current print job information from the session and
    renders the `order_summary.html` template. We use session values
    stored earlier during settings so the user can review pricing.
    """
    uploaded_filename = session.get("uploaded_filename")
    copies = session.get("copies")
    print_type = session.get("print_type")
    paper_size = session.get("paper_size")
    orientation = session.get("orientation", "portrait")
    pages_per_sheet = session.get("pages_per_sheet", "1")
    print_sides = session.get("print_sides", "single")
    price_per_page = session.get("price_per_page")
    number_of_pages = session.get("number_of_pages")
    total_price = session.get("total_price")

    return render_template(
        "order_summary.html",
        uploaded_filename=uploaded_filename,
        copies=copies,
        print_type=print_type,
        paper_size=paper_size,
        orientation=orientation,
        pages_per_sheet=pages_per_sheet,
        print_sides=print_sides,
        price_per_page=price_per_page,
        number_of_pages=number_of_pages,
        total_price=total_price,
    )


@app.route("/payment", methods=["GET", "POST"])
def payment():
    """Payment page and test confirmation handler.

    GET: render the payment page showing order details from the session.
    POST: treat as a TEST payment confirmation (no real gateway). We
    mark the session as paid, generate a secure 6-digit passcode using
    Python's `secrets` module, store it in the session, and redirect
    the user to the `/passcode` page.
    """
    uploaded_filename = session.get("uploaded_filename")
    copies = session.get("copies")
    print_type = session.get("print_type")
    paper_size = session.get("paper_size")
    orientation = session.get("orientation", "portrait")
    pages_per_sheet = session.get("pages_per_sheet", "1")
    print_sides = session.get("print_sides", "single")
    number_of_pages = session.get("number_of_pages")
    total_price = session.get("total_price")

    required_order_data_exists = all(
        [
            uploaded_filename,
            copies is not None,
            print_type,
            paper_size,
            number_of_pages is not None,
            total_price is not None,
        ]
    )

    error = None
    if request.method == "POST":
        if not required_order_data_exists:
            error = (
                "Order information is incomplete. Please return to order "
                "summary and confirm your print settings."
            )
        else:
            # Payment is simulated in this prototype. No real payment
            # gateway is integrated yet.
            session["payment_status"] = "paid"

            # Generate a secure 6-digit numeric passcode for kiosk release.
            # We avoid values with leading zeros so the code remains valid
            # even when the browser coerces numeric input values.
            passcode = str(secrets.randbelow(900000) + 100000)
            session["passcode"] = passcode

            return redirect(url_for("passcode"))

    # GET: render payment page using values stored in the session.
    return render_template(
        "payment.html",
        uploaded_filename=uploaded_filename,
        copies=copies,
        print_type=print_type,
        paper_size=paper_size,
        orientation=orientation,
        pages_per_sheet=pages_per_sheet,
        print_sides=print_sides,
        number_of_pages=number_of_pages,
        total_price=total_price,
        error=error,
        required_order_data_exists=required_order_data_exists,
    )


@app.route("/passcode")
def passcode():
    """Display the generated passcode after a TEST payment.

    Reads the `passcode` from the session and renders `passcode.html`.
    This page tells the customer the code they should enter at the
    kiosk to release the print job.
    """
    generated_passcode = session.get("passcode")
    return render_template("passcode.html", passcode=generated_passcode)


@app.route("/verify-passcode", methods=["GET", "POST"])
def verify_passcode():
    """Verify the 6-digit passcode entered by the customer.

    - GET: show the verification form (only when a passcode exists
      in the session and payment_status is 'paid').
    - POST: read the submitted passcode from `request.form`, compare
      it to the passcode stored in `session['passcode']`, and set
      `session['passcode_verified']` when correct.

    Beginner-friendly comments in this handler explain key concepts:
    - GET vs POST: GET displays pages; POST handles form submissions.
    - `request.form` is how Flask exposes submitted form fields.
    - `session['passcode']` stores the original generated code.
    - `passcode_verified` is a simple session flag we set on success.
    """

    # Check that a passcode was generated and payment was confirmed.
    stored_passcode = session.get("passcode")
    payment_status = session.get("payment_status")

    # If there is no passcode or payment isn't marked paid, we should
    # not allow verification. Show an informative message instead.
    if not stored_passcode or payment_status != "paid":
        info = None
        if not stored_passcode:
            info = "No passcode found. Please complete payment first."
        else:
            info = "Payment not confirmed. Passcode verification is not allowed."

        # Render the template with an informational message and do not
        # show/accept verification attempts.
        return render_template(
            "verify_passcode.html",
            info=info,
            show_form=False,
        )

    # At this point we have a stored passcode and payment is 'paid'.

    # If the passcode was already verified in this session, there is no
    # need to show the form again — redirect the user to the print page.
    if session.get("passcode_verified"):
        return redirect(url_for("print_page"))

    error = None

    if request.method == "POST":
        # Read the passcode entered by the customer from the form.
        # `request.form` is a dict-like object with submitted form values.
        entered = request.form.get("passcode", "").strip()

        # Normalize: ensure it's a 6-digit numeric string before comparing.
        if not entered.isdigit() or len(entered) != 6:
            error = "Please enter a valid 6-digit passcode."
        else:
            # Compare the entered passcode to the one stored in session.
            # Use string equality because both values are stored as strings.
            if entered == stored_passcode:
                # Mark the passcode as verified in the session. This is a
                # simple flag other parts of the app can check later.
                session["passcode_verified"] = True

                # Do not start any printer or delete files here — per
                # requirements we only set the flag and redirect the user
                # to the `/print` page where they can confirm printing.
                return redirect(url_for("print_page"))
            else:
                # Incorrect passcode: stay on this page and show the form
                # again with an error message so the user can retry.
                error = "Incorrect passcode. Please try again."

    # Render the verification page. The template will show the form
    # (when `show_form` is True) and any `error` message.
    return render_template(
        "verify_passcode.html",
        show_form=True,
        error=error,
    )


@app.route("/api/print-job", methods=["GET"])
def print_job_api():
    """Return the current print job as JSON for future Pi integration.

    An API (Application Programming Interface) is a structured way for
    different software programs to communicate with each other. Here, the
    Flask app exposes job details as JSON so another system, such as a
    Raspberry Pi later on, can read the job without needing to scrape the
    HTML pages.

    JSON is used because it is lightweight, easy to read, and widely
    supported by Python, JavaScript, and Raspberry Pi code.

    This route intentionally does not return the actual file contents. It
    only sends the file path and print metadata so the document itself stays
    secure and the API remains focused on job coordination rather than file
    transfer. In the future, the Raspberry Pi can call this API to learn
    what is ready to print and then process the document separately.
    """
    uploaded_filename = session.get("uploaded_filename") 

    if not uploaded_filename:
        return jsonify({"error": "No uploaded file/job exists."}), 404

    if session.get("payment_status") != "paid":
        return jsonify({"error": "Payment has not been completed."}), 403

    if not session.get("passcode_verified"):
        return jsonify({"error": "Passcode has not been verified."}), 403

    print_job = {
        "filename": uploaded_filename,
        "file_path": os.path.join("uploads", uploaded_filename),
        "number_of_pages": session.get("number_of_pages"),
        "copies": session.get("copies"),
        "total_printable_pages": (session.get("number_of_pages") or 1) * (session.get("copies") or 1),
        "print_type": session.get("print_type"),
        "paper_size": session.get("paper_size"),
        "orientation": session.get("orientation", "portrait"),
        "pages_per_sheet": session.get("pages_per_sheet", "1"),
        "print_sides": session.get("print_sides", "single"),
        "price_per_page": session.get("price_per_page"),
        "total_price": session.get("total_price"),
        "payment_status": session.get("payment_status"),
        "passcode_verified": bool(session.get("passcode_verified")),
        "print_status": "ready",
    }

    return jsonify(print_job), 200


@app.route("/print", methods=["GET", "POST"])
def print_page():
    """Ready-to-print page.

    This route is only accessible when the user has completed payment
    and the kiosk passcode has been verified. We check the session for
    `payment_status` and `passcode_verified` and redirect back to the
    verification page when those conditions are not met.

    Beginner-friendly note: we require passcode verification before
    allowing access to the print page to prevent unauthorized release
    of uploaded documents.
    """

    # Enforce access control using session flags. Only allow access
    # when payment is marked 'paid' and the passcode has been verified.
    if session.get("payment_status") != "paid" or not session.get("passcode_verified"):
        return redirect(url_for("verify_passcode"))

    # Read the print job info from the session to display on the page.
    uploaded_filename = session.get("uploaded_filename")
    copies = session.get("copies")
    print_type = session.get("print_type")
    paper_size = session.get("paper_size")

    # Handle POST when the user clicks "Print Document" to perform
    # a TEST print. We simulate printing, then delete the uploaded
    # file and clear the session so the kiosk is ready for the next
    # customer.
    if request.method == "POST":
        # Ensure we still have the uploaded filename in the session.
        filename = uploaded_filename

        if not filename:
            # No filename in session — cannot proceed.
            error = "No uploaded file found for printing."
            return render_template(
                "print.html",
                uploaded_filename=uploaded_filename,
                copies=copies,
                print_type=print_type,
                paper_size=paper_size,
                error=error,
            )

        # Build the path to the uploaded file using os.path.join.
        # This keeps path assembly platform-independent.
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # Check whether the file exists before attempting to delete it.
        # os.path.exists() returns True when the path points to a file.
        if not os.path.exists(file_path):
            # File missing — do not pretend printing succeeded.
            error = "Uploaded file is missing; cannot print."
            return render_template(
                "print.html",
                uploaded_filename=uploaded_filename,
                copies=copies,
                print_type=print_type,
                paper_size=paper_size,
                error=error,
            )

        # Simulate printing here. In a real system we'd send the file
        # to the printer and wait for confirmation. Only after the
        # print operation succeeds should we delete the temporary file.
        # For this test flow we assume the simulated print succeeds.

        try:
            # Delete the uploaded file to remove temporary data.
            # os.remove() deletes the file at the given path.
            os.remove(file_path)
        except OSError:
            # If deletion failed, show an error rather than claiming
            # success. Do not clear the session in this case.
            error = "Failed to remove temporary file after printing."
            return render_template(
                "print.html",
                uploaded_filename=uploaded_filename,
                copies=copies,
                print_type=print_type,
                paper_size=paper_size,
                error=error,
            )

        # Clear the user's session so the kiosk resets for the next
        # customer. session.clear() removes all stored session keys.
        session.clear()

        # Show the print completion page describing what happened.
        return render_template("print_complete.html")

    # GET: render the page showing print job details and the test
    # "Print Document" button. Pass `error=None` when nothing is wrong.
    return render_template(
        "print.html",
        uploaded_filename=uploaded_filename,
        copies=copies,
        print_type=print_type,
        paper_size=paper_size,
        error=None,
    )


if __name__ == "__main__":
    app.run(debug=True)
