import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createMeeting,
  deleteMeeting,
  fetchMeetings,
  updateMeeting,
  uploadMeetingMinutes,
} from '../../services/api';
import { queryKeys } from '../../lib/api/queryKeys';
import type { Meeting } from '../../types';

const meetingsKey = (includePast: boolean) => [...queryKeys.meetings, includePast] as const;

export const useMeetingsQuery = (includePast = true) =>
  useQuery<Meeting[]>({
    queryKey: meetingsKey(includePast),
    queryFn: () => fetchMeetings(includePast),
  });

const useInvalidateMeetings = () => {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.meetings });
};

export const useCreateMeetingMutation = () => {
  const invalidate = useInvalidateMeetings();
  return useMutation({
    mutationFn: createMeeting,
    onSuccess: invalidate,
  });
};

export const useDeleteMeetingMutation = () => {
  const invalidate = useInvalidateMeetings();
  return useMutation({
    mutationFn: (meetingId: number) => deleteMeeting(meetingId),
    onSuccess: invalidate,
  });
};

export const useUploadMinutesMutation = () => {
  const invalidate = useInvalidateMeetings();
  return useMutation({
    mutationFn: ({ meetingId, file }: { meetingId: number; file: File }) =>
      uploadMeetingMinutes(meetingId, file),
    onSuccess: invalidate,
  });
};

export const useUpdateMeetingMutation = () => {
  const invalidate = useInvalidateMeetings();
  return useMutation({
    mutationFn: ({
      meetingId,
      payload,
    }: {
      meetingId: number;
      payload: Partial<{
        title: string;
        description: string | null;
        start_time: string;
        end_time: string | null;
        location: string | null;
        zoom_link: string | null;
      }>;
    }) => updateMeeting(meetingId, payload),
    onSuccess: invalidate,
  });
};
