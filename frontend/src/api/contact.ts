import { api } from "./client";

export interface ContactSubmissionPayload {
  name: string;
  email: string;
  company?: string;
  message: string;
}

export interface ContactSubmissionResponse {
  id: string;
  message: string;
}

export const contactApi = {
  submit: (payload: ContactSubmissionPayload) =>
    api
      .post<ContactSubmissionResponse>("/contact", payload)
      .then((r) => r.data),
};
